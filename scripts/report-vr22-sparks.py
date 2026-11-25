#!/usr/bin/env python3
"""Package the spark study for vr22-06 through vr22-13."""

import argparse
import csv
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blackbox"))
from optical_summary import CONDITION_COLUMNS, read_optical_values, write_text_summary

RUNS = tuple(f"vr22-{number:02d}" for number in range(6, 14))
PAIRED_PLOTS = (
    "x_projection_signal.png", "y_projection_signal.png", "combined_integral_distribution.png",
)
DIAGNOSTICS = (
    "tot-distribution-before-sparks.png",
    "tot-vs-time-spark-removal.png",
)
SUMMARY_COLUMNS = (
    "run", "spark_count", "spark_algorithm_iterations", "removal_applied", "exposure_before_s",
    "exposure_after_s", "exposure_excluded_s", "S_O_ms", "S_O_norm_ms_per_s",
    "S_O_norm_rms_ms_per_s", "S_O_error_in_percentage",
    "percentage_of_removed_exposure", *CONDITION_COLUMNS, "issues",
)
def write_csv(path, fields, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def copy_plot(source, destination, issues):
    if source.is_file():
        shutil.copy2(source, destination)
    else:
        issues.append(f"missing {destination.name}")


def copy_run_plots(before_plots, after_plots, diagnostics, destination, issues):
    """Copy the nine per-run figures with explicit before/after filenames."""
    name = "2D_integrated_ToT.png"
    copy_plot(after_plots / name, destination / name, issues)
    for name in DIAGNOSTICS:
        source = after_plots / name
        if not source.is_file():
            source = diagnostics / name
        copy_plot(source, destination / name, issues)
    for name in PAIRED_PLOTS:
        for phase, folder in (("before", before_plots), ("after", after_plots)):
            output = destination / f"{Path(name).stem}_{phase}.png"
            copy_plot(folder / name, output, issues)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="dataset results directory with spark removal off")
    parser.add_argument("after", type=Path, help="dataset results directory with spark removal on")
    parser.add_argument("output", type=Path, help="new report directory")
    parser.add_argument("--runs", nargs="+", choices=RUNS, default=RUNS)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    summary, windows = [], []

    for run in dict.fromkeys(args.runs):
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
            row.update(removal_applied=report["Removal applied"],
                       exposure_before_s=before, exposure_after_s=after,
                       exposure_excluded_s=float(report["Exposure excluded (s)"]))
            if "Hits above ToT cut" in report:
                row["spark_count"] = int(report["Hits above ToT cut"])
            elif report.get("Spark count rule", "").startswith("individual hits"):
                row["spark_count"] = int(report["Spark count"])
            else:
                issues.append("spark count unavailable in this report")
            if "Spark algorithm iterations" in report:
                row["spark_algorithm_iterations"] = int(report["Spark algorithm iterations"])
            elif "ToT cut (strictly greater than)" in report:
                # Earlier ToT-cut reports omitted the count but used the same single pass.
                row["spark_algorithm_iterations"] = 1
            else:
                issues.append("spark algorithm iteration count unavailable")
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
            row.update(read_optical_values(cleaned, run))
        except (OSError, ValueError, IndexError, StopIteration) as error:
            issues.append(f"optical integral unavailable: {error}")

        before_plots = args.before / "plots" / "optical_per_run" / run
        copy_run_plots(before_plots, plots, cleaned / "diagnostics", destination, issues)
        row["issues"] = "; ".join(issues)
        write_text_summary(destination / "run_summary.txt", row)
        print(f"{run}: spark count {row.get('spark_count', 'unavailable')}"
              + (f" ({row['issues']})" if issues else ""))

    write_csv(args.output / "run_summary.csv", SUMMARY_COLUMNS, summary)
    write_csv(args.output / "excluded_intervals.csv",
              ("run", "interval", "start_s", "stop_s", "excluded_exposure_s"), windows)
    return int(any(row["issues"] for row in summary))


if __name__ == "__main__":
    raise SystemExit(main())
