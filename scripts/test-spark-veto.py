#!/usr/bin/env python3
"""Test the padded spark veto: remove hits from BEFORE s before to AFTER s after each spark.

The grouped spark cut flags 5 ms windows (summed ToT > mean + 10 RMS). With a
veto, every hit in [window start - BEFORE, window end + AFTER) is removed and
overlapping vetoes are merged; the exposure loses the union of the vetoes
inside the run.

  # synthetic checks only (no data needed)
  python3 scripts/test-spark-veto.py --self-test

  # compare the standard cut with a -1 s / +20 s veto on real runs
  python3 scripts/test-spark-veto.py -o veto-test \
      ~/warTPC/data/voltage-run-22-11-26/optical/vr22-07/output.hdf5 ...

Per run, <out>/<run>/baseline/ and <out>/<run>/veto/ get spark_status.txt and
the ToT plots; <out>/summary.csv compares the two. The HDF5 files are only read.
The same veto can be used in the full pipeline with
WARTPC_SPARK_VETO_BEFORE_S=1 WARTPC_SPARK_VETO_AFTER_S=20 bash scripts/workflow.sh ...
"""

import argparse
import csv
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "blackbox"))
os.environ["WARTPC_SPARK_METHOD"] = "grouped"

from matplotlib import use  # noqa: E402

use("Agg")

from spark_detection import TOA_TICKS_PER_SECOND as TICKS, spark_cut  # noqa: E402


def run_cut(toa, tot, folder, before, after):
    keep, duration, excluded = spark_cut(toa, tot, Path(folder) / "spark_status.txt",
                                         mode="remove", veto_before=before, veto_after=after)
    kept = int(keep.sum()) if keep is not None else len(toa)
    return keep, kept, duration, excluded


def self_test():
    """Synthetic run: 300 s of steady hits with sparks at 50 s, 50.5 s and 299.9 s."""
    rng = np.random.default_rng(1)
    seconds = np.sort(rng.uniform(0, 300, 200_000))
    seconds[0], seconds[-1] = 0.0, 300.0
    tot = rng.integers(20, 40, seconds.size).astype(float)
    sparks = (50.0021, 50.5021, 299.9021)  # inside the 5 ms windows starting at 50.000, 50.500, 299.900
    extra_s = np.concatenate([np.full(400, s) for s in sparks])
    seconds = np.concatenate([seconds, extra_s])
    tot = np.concatenate([tot, np.full(extra_s.size, 1000.0)])
    order = np.argsort(seconds, kind="stable")
    seconds, tot = seconds[order], tot[order]
    toa = np.round(seconds * TICKS).astype(np.int64)

    failures = []

    def check(name, ok):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        keep0, _, duration, excl0 = run_cut(toa, tot, f"{tmp}/baseline", 0, 0)
        keep1, _, _, excl1 = run_cut(toa, tot, f"{tmp}/veto", 1, 20)
        keep_env = None
        os.environ["WARTPC_SPARK_VETO_BEFORE_S"] = "1"
        os.environ["WARTPC_SPARK_VETO_AFTER_S"] = "20"
        try:
            keep_env, *_ = spark_cut(toa, tot, Path(tmp) / "env" / "spark_status.txt", mode="remove")
        finally:
            del os.environ["WARTPC_SPARK_VETO_BEFORE_S"], os.environ["WARTPC_SPARK_VETO_AFTER_S"]
        report = (Path(tmp) / "veto" / "spark_status.txt").read_text()

    elapsed = (toa - toa[0]) / TICKS
    # Expected: [49, 70.505) merged from the two 50 s sparks, and [298.9, 300] at the end.
    expected_removed = ((elapsed >= 49.0) & (elapsed < 70.505)) | (elapsed >= 298.9)
    check("baseline flags the three 5 ms spark windows", "Candidate intervals: 3" in report)
    check("baseline removes only hits inside the 5 ms windows",
          np.array_equal(~keep0, np.isin(np.floor(elapsed / 0.005), np.floor(np.array(sparks) / 0.005))))
    check("baseline excludes 15 ms", abs(excl0 - 0.015) < 1e-9)
    check("veto removes hits 1 s before to 20 s after each window", np.array_equal(~keep1, expected_removed))
    check("overlapping vetoes merge into two intervals", "Merged veto intervals: 2" in report)
    check("veto exposure = 21.505 s + 1.1 s (clipped at the run end)", abs(excl1 - 22.605) < 1e-6)
    check("exposure before the cut is 300 s", abs(duration - 300.0) < 1e-9)
    check("environment variables give the same mask", keep_env is not None and np.array_equal(keep_env, keep1))
    print("Self-test", "FAILED" if failures else "passed")
    return not failures


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("hdf5", type=Path, nargs="*", help="optical <run>/output.hdf5 files")
    parser.add_argument("-o", "--output", type=Path, help="output directory for reports and plots")
    parser.add_argument("--before", type=float, default=1.0, help="seconds removed before each spark (default 1)")
    parser.add_argument("--after", type=float, default=20.0, help="seconds removed after each spark (default 20)")
    parser.add_argument("--self-test", action="store_true", help="run the synthetic checks")
    args = parser.parse_args()
    if not args.self_test and not args.hdf5:
        parser.error("give HDF5 files and -o, or --self-test")
    ok = self_test() if args.self_test else True
    if not args.hdf5:
        return 0 if ok else 1
    if args.output is None:
        parser.error("-o is required with HDF5 files")

    import h5py

    rows = []
    for path in args.hdf5:
        run = path.parent.name
        try:
            with h5py.File(path, "r") as source:
                toa, tot = source["PixelHits"]["toa"][:], source["PixelHits"]["tot"][:]
        except (OSError, KeyError) as error:
            print(f"{run}: cannot read {path}: {error}", file=sys.stderr)
            ok = False
            continue
        print(f"=== {run} ===")
        try:
            _, kept0, duration, excl0 = run_cut(toa, tot, args.output / run / "baseline", 0, 0)
            _, kept1, _, excl1 = run_cut(toa, tot, args.output / run / "veto", args.before, args.after)
        except ValueError as error:  # e.g. the veto would leave no exposure
            print(f"{run}: {error}", file=sys.stderr)
            ok = False
            continue
        rows.append(dict(
            run=run, hits=len(toa), exposure_s=f"{duration:.9g}",
            baseline_hits_kept=kept0, baseline_exposure_excluded_s=f"{excl0:.9g}",
            veto_hits_kept=kept1, veto_exposure_excluded_s=f"{excl1:.9g}",
            veto_removed_exposure_fraction=f"{excl1 / duration:.6g}" if duration else "",
        ))
    if rows:
        args.output.mkdir(parents=True, exist_ok=True)
        with (args.output / "summary.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nVeto -{args.before:g} s / +{args.after:g} s")
        print(f"{'run':<10}{'hits':>12}{'kept (std)':>13}{'kept (veto)':>13}{'excl s (veto)':>15}{'frac':>9}")
        for row in rows:
            print(f"{row['run']:<10}{row['hits']:>12,}{row['baseline_hits_kept']:>13,}"
                  f"{row['veto_hits_kept']:>13,}{float(row['veto_exposure_excluded_s']):>15.3f}"
                  f"{float(row['veto_removed_exposure_fraction'] or 0):>9.1%}")
        print(f"Summary: {args.output / 'summary.csv'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
