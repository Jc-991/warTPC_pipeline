"""Count high-ToT bursts and optionally exclude individual ToT outliers."""

from pathlib import Path
import os

import numpy as np


SPARK_TOT_THRESHOLD = 8000
SPARK_GAP_TICKS = 500_000_000_000  # 50 ms in the stored ToA units
TOT_CUT_RMS = 10


def count_sparks(toa, tot):
    """Count clusters of at least two high-ToT hits in the original data."""
    high_toa = np.sort(toa[tot >= SPARK_TOT_THRESHOLD])
    groups = np.split(high_toa, np.flatnonzero(np.diff(high_toa) > SPARK_GAP_TICKS) + 1)
    return sum(len(group) >= 2 for group in groups)


def save_tot_distribution(tot, output, removed=None):
    """Histogram the measured ToT of every original hit."""
    from matplotlib import pyplot as plt

    counts, edges = np.histogram(tot, bins=128)
    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
    try:
        mean = float(np.mean(tot))
        rms = float(np.std(tot))
        lower, upper = mean - 5 * rms, mean + 5 * rms
        if removed is None:
            ax.stairs(counts, edges, fill=True, color="tab:blue", label="All hits before tagging")
        else:
            removed_counts, _ = np.histogram(tot[removed], bins=edges)
            kept_counts = counts - removed_counts
            ax.stairs(kept_counts, edges, fill=True, color="tab:blue",
                      label=f"Kept ({int((~removed).sum()):,} hits)")
            ax.stairs(counts, edges, baseline=kept_counts, fill=True, color="tab:red",
                      label=f"Removed ({int(removed.sum()):,} hits)")
        ax.axvline(lower, color="black", linestyle="--", label=f"Mean − 5 RMS ({lower:.1f})")
        ax.axvline(upper, color="black", linestyle=":", label=f"Mean + 5 RMS ({upper:.1f})")
        cutoff = mean + TOT_CUT_RMS * rms
        ax.axvline(cutoff, color="tab:red", linestyle="--", label=f"ToT cut ({cutoff:.1f})")
        left, right = min(edges[0], lower), max(edges[-1], cutoff)
        padding = 0.02 * (right - left)
        ax.set(xlabel="Hit ToT (stored units)", ylabel="Hits per bin",
               xlim=(left - padding, right + padding), yscale="log",
               title="Hit ToT distribution and spark cut")
        ax.legend()
        fig.savefig(output, dpi=170)
    finally:
        plt.close(fig)


def save_tot_spectrum(seconds, tot, time_bins, width, output, removed=None):
    """Plot the unfiltered ToT distribution as a function of run time."""
    from matplotlib import pyplot as plt
    from matplotlib.colors import LogNorm

    edges = np.arange(time_bins + 1) * width
    counts, _, tot_edges = np.histogram2d(seconds, tot, bins=(edges, 128))
    fig, ax = plt.subplots(figsize=(12, 4), layout="constrained")
    try:
        image = ax.imshow(
            counts.T, origin="lower", aspect="auto", interpolation="nearest",
            extent=(edges[0], edges[-1], tot_edges[0], tot_edges[-1]),
            norm=LogNorm(vmin=1, vmax=max(2, counts.max())),
        )
        fig.colorbar(image, ax=ax, label="Hits per bin")
        ax.set(xlabel="Time since first hit (s)", ylabel="Hit ToT (stored units)",
               title="ToT versus arrival time before spark tagging")
        if removed is not None:
            ax.scatter(seconds[removed], tot[removed], s=24, facecolors="none",
                       edgecolors="tab:red", linewidths=0.8,
                       label=f"Removed hits ({int(removed.sum()):,})")
            ax.set_title("ToT versus arrival time with removed hits marked")
            ax.legend(loc="upper right")
        fig.savefig(output, dpi=170)
    finally:
        plt.close(fig)


def spark_cut(toa, tot, report_path, *, mode=None):
    """Return the optional keep mask, original exposure, and excluded seconds."""
    if mode is None:
        mode = os.environ.get("WARTPC_SPARK_MODE", "off").strip().lower()
    if mode not in ("off", "detect", "remove"):
        raise ValueError("WARTPC_SPARK_MODE must be off, detect, or remove")

    width = 0.01
    count = len(toa)
    duration = 0.0
    cutoff = None
    flagged = None
    keep = None
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    if count:
        if mode == "off":
            duration = (int(toa[-1]) - int(toa[0])) / 1e13
        else:
            seconds = (toa - toa.min()) / 1e13
            duration = float(seconds.max())
            bins = (seconds / width).astype(np.intp)
            time_bins = int(bins.max()) + 1
            save_tot_spectrum(seconds, tot, time_bins, width,
                              report.with_name("tot-vs-time-before-sparks.png"))
            cutoff = float(np.mean(tot) + TOT_CUT_RMS * np.std(tot))
            flagged = tot > cutoff
            if mode == "remove" and flagged.any():
                keep = ~flagged

    excluded = 0.0  # An individual-hit cut does not veto any time intervals.
    remaining = int(keep.sum()) if keep is not None else count
    removed = count - remaining
    usable = duration - excluded
    rejected = mode == "remove" and (remaining == 0 or usable <= 0)
    if rejected:
        status = "rejected: no hits or usable exposure would remain"
    elif removed:
        status = "yes"
    elif mode == "remove":
        status = "no (no hits above the ToT cut)"
    else:
        status = f"no ({mode} mode)"
    sparks = count_sparks(toa, tot)
    lines = [
        f"Mode: {mode}",
        f"Removal applied: {status}",
        f"Spark count: {sparks}",
        "Candidate intervals: 0",
        f"Hits before/kept: {count} / {remaining}",
        f"Hits excluded: {removed}",
        f"Exposure before/after (s): {duration:.9g} / {usable:.9g}",
        f"Exposure excluded (s): {excluded:.9g}",
    ]
    lines.append(f"Spark count rule: at least two hits with ToT >= {SPARK_TOT_THRESHOLD}, grouped across gaps of up to 50 ms")
    if cutoff is not None:
        lines.append(f"ToT cut (strictly greater than): {cutoff:.9g}")
        lines.append(f"Hits above ToT cut: {int(flagged.sum())}")
    report.write_text("\n".join(lines) + "\n")
    print(f"Spark mode: {mode}; spark count: {sparks}; removal applied: {status}; report: {report}", flush=True)
    if rejected:
        raise ValueError(f"Spark cut rejected; see {report}")
    if count and mode != "off":
        removed_mask = None
        if mode == "remove":
            removed_mask = ~keep if keep is not None else np.zeros(count, dtype=bool)
            save_tot_spectrum(seconds, tot, time_bins, width,
                              report.with_name("tot-vs-time-spark-removal.png"),
                              removed=removed_mask)
        save_tot_distribution(tot, report.with_name("tot-distribution-before-sparks.png"), removed_mask)
    return keep, duration, excluded


if __name__ == "__main__":
    import argparse
    import csv
    import h5py
    import sys

    parser = argparse.ArgumentParser(description="Count high-ToT sparks in saved optical runs.")
    parser.add_argument("--fallback-optical", type=Path,
                        help="try <dir>/<run>/output.hdf5 when a primary file is unreadable")
    parser.add_argument("--csv", type=Path, help="write counts to this CSV")
    parser.add_argument("--removal-plots", type=Path,
                        help="save plots and the ToT cut report for one HDF5 file to this directory")
    parser.add_argument("hdf5", type=Path, nargs="+")
    args = parser.parse_args()
    if args.removal_plots is not None and len(args.hdf5) != 1:
        parser.error("--removal-plots requires exactly one HDF5 file")
    failed = False
    rows = []
    for path in args.hdf5:
        run = path.parent.name
        sources = [path]
        if args.fallback_optical is not None:
            sources.append(args.fallback_optical / run / "output.hdf5")
        for index, source_path in enumerate(sources):
            try:
                with h5py.File(source_path, "r") as source:
                    hits = source["PixelHits"]
                    toa, tot = hits["toa"][:], hits["tot"][:]
                    count = count_sparks(toa, tot)
            except (OSError, KeyError, ValueError) as error:
                print(f"{run}: cannot read {source_path}: {error}", file=sys.stderr, flush=True)
                continue
            suffix = " (before-pass HDF5)" if index else ""
            if args.removal_plots is not None:
                from matplotlib import use

                use("Agg")
                spark_cut(toa, tot, args.removal_plots / "spark_status.txt", mode="remove")
            print(f"{run}: {count}{suffix}", flush=True)
            rows.append((run, count))
            break
        else:
            failed = True
            print(f"{run}: spark count unavailable", flush=True)
            rows.append((run, ""))
    if args.csv is not None:
        with args.csv.open("w", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(("run", "spark_count"))
            writer.writerows(rows)
    sys.exit(int(failed))
