#!/usr/bin/env python3
"""Package the spark study for vr22-06 through vr22-13."""

import argparse
import csv
from pathlib import Path
import re
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


PLOTS = (
    "2D_integrated_ToT.png",
    "combined_integral_distribution.png",
    "x_projection_signal.png",
    "y_projection_signal.png",
    "tot-vs-time-before-sparks.png",
)
SUMMARY_COLUMNS = (
    "run", "candidate_intervals", "removal_applied", "exposure_before_s",
    "exposure_after_s", "exposure_excluded_s", "S_O_ms", "S_O_norm_ms_per_s",
    "S_O_norm_rms_ms_per_s", "issues",
)


def write_csv(path, fields, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def compare_x(before, after, output, run):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    try:
        for ax, source, title in zip(axes, (before, after), ("Before spark removal", "After spark removal")):
            ax.imshow(plt.imread(source))
            ax.set_title(title)
            ax.axis("off")
        fig.suptitle(f"{run} · Background-subtracted X projection")
        fig.savefig(output, dpi=160)
    finally:
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="dataset results directory with spark removal off")
    parser.add_argument("after", type=Path, help="dataset results directory with spark removal on")
    parser.add_argument("output", type=Path, help="new report directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    summary, windows = [], []

    for number in range(6, 14):
        run = f"vr22-{number:02d}"
        cleaned = args.after / "optical" / run
        plots = args.after / "plots" / "optical_per_run" / run
        destination = args.output / "optical_per_run" / run
        destination.mkdir(parents=True)
        row = {"run": run}
        issues = []
        summary.append(row)
        try:
            text = (cleaned / "diagnostics" / "spark_status.txt").read_text()
            report = dict(line.split(": ", 1) for line in text.splitlines() if ": " in line)
            if report["Mode"] != "remove":
                issues.append("spark mode was not remove")
            count = int(report["Candidate intervals"])
            before, after = map(float, report["Exposure before/after (s)"].split(" / "))
            row.update(candidate_intervals=count, removal_applied=report["Removal applied"],
                       exposure_before_s=before, exposure_after_s=after,
                       exposure_excluded_s=float(report["Exposure excluded (s)"]))
            if report["Removal applied"].startswith("rejected"):
                issues.append(report["Removal applied"])
            intervals = re.findall(r"^Candidate since first hit \(s\): (\S+) to (\S+)$", text, re.M)
            if len(intervals) != count:
                issues.append("candidate count differs from interval list")
            if report["Removal applied"] == "yes":
                for index, (start, stop) in enumerate(intervals, 1):
                    windows.append(dict(run=run, interval=index, start_s=start, stop_s=stop,
                                        excluded_exposure_s=f"{float(stop) - float(start):.9g}"))
        except (OSError, KeyError, ValueError) as error:
            issues.append(f"spark report: {error}")
        try:
            with (cleaned / "integral.csv").open(newline="") as handle:
                values = next(csv.reader(handle))
            normalized = float(values[8])
            exposure = float(values[15])
            row.update(S_O_ms=normalized * exposure, S_O_norm_ms_per_s=normalized,
                       S_O_norm_rms_ms_per_s=float(values[9]))
        except (OSError, ValueError, IndexError, StopIteration) as error:
            issues.append(f"optical integral unavailable: {error}")

        for name in PLOTS:
            source = plots / name
            if name == PLOTS[-1] and not source.is_file():
                source = cleaned / "diagnostics" / name
            if source.is_file():
                shutil.copy2(source, destination / name)
            else:
                issues.append(f"missing {name}")
        before_x = args.before / "plots" / "optical_per_run" / run / "x_projection_signal.png"
        after_x = plots / "x_projection_signal.png"
        if before_x.is_file() and after_x.is_file():
            compare_x(before_x, after_x, destination / "x_projection_before_after.png", run)
        else:
            issues.append("missing before/after X projection")
        row["issues"] = "; ".join(issues)
        print(f"{run}: {row['issues'] or str(row.get('candidate_intervals')) + ' candidate intervals'}")

    write_csv(args.output / "run_summary.csv", SUMMARY_COLUMNS, summary)
    write_csv(args.output / "excluded_intervals.csv",
              ("run", "interval", "start_s", "stop_s", "excluded_exposure_s"), windows)
    return int(any(row["issues"] for row in summary))


if __name__ == "__main__":
    raise SystemExit(main())
