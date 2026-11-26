#!/usr/bin/env python3
"""Generate comparison overlays from explicitly selected optical exports."""

import argparse
from pathlib import Path
import runpy
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plotting"))
import plot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", action="append", default=[], metavar="PATH",
                        help="results.csv or its plots folder; repeat for each dataset")
    parser.add_argument("--series", nargs=2, action="append", default=[],
                        metavar=("LABEL", "PATH"), help="legend label and results.csv or its plots folder")
    parser.add_argument("-o", "--output", type=Path, required=True,
                        help="new or empty comparison output folder")
    parser.add_argument("--paper-image", type=Path,
                        help="optional calibrated Figure 26 image; existing markers remain visible")
    args = parser.parse_args()
    if not (args.input or args.series):
        parser.error("provide at least one -i PATH or --series LABEL PATH")
    output = args.output.expanduser()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error(f"output must be a new or empty directory: {output}")

    rows, sources, labels = [], [], set()
    metrics = ("optical", *plot.OPTIONAL_METRICS)
    for label, name in [*((None, name) for name in args.input), *args.series]:
        path = Path(name).expanduser().resolve()
        if path.is_dir():
            path /= "results.csv"
        if not path.is_file():
            parser.error(f"results CSV not found: {path}")
        selected = [row for row in plot.load_results(path, dataset=label) if not row["excluded"]]
        if label is None:
            datasets = {row["dataset"] for row in selected}
            if len(datasets) != 1 or "" in datasets:
                parser.error(f"could not select one dataset name from {path}; use --series LABEL PATH")
            label = next(iter(datasets))
            for folder, phase in (("recovered-before", "before cut"),
                                  ("recovered-after", "after cut"),
                                  ("recovered-saved", "saved fit")):
                if folder in path.parts:
                    label = f"{label} ({phase})"
                    break
            for row in selected:
                row["dataset"] = label
        if label in labels:
            parser.error(f"duplicate series label: {label}; use --series with distinct labels")
        labels.add(label)
        if not any(row.get("v_over_p") is not None and any(row.get(metric) is not None for metric in metrics)
                   for row in selected):
            parser.error(f"no usable optical points for {label} in {path}")
        rows.extend(selected)
        sources.append(dict(series=label, results_csv=str(path), run_rows=len(selected)))

    paper = args.paper_image.expanduser() if args.paper_image else None
    if paper is not None and not paper.is_file():
        parser.error(f"paper image not found: {paper}")
    metrics = [metric for metric in metrics if any(
        row.get(metric) is not None and row.get("v_over_p") is not None for row in rows
    )]
    warnings = []
    plot.comparison_plots(rows, output, paper, warnings, [], metrics=metrics)
    organiser = runpy.run_path(str(REPO / "scripts" / "organise-optical-plots.py"))
    organiser["add_plot_ids"](output, "C", organiser["COMPARISON_PLOT_ORDER"])
    plot.write_csv(output / "sources.csv", sources, ("series", "results_csv", "run_rows"))
    (output / "warnings.txt").write_text("\n".join(warnings) + "\n" if warnings else "No warnings.\n")
    print(f"Comparisons: {output}")


if __name__ == "__main__":
    main()
