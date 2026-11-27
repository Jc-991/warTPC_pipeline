#!/usr/bin/env python3
"""Generate comparisons from explicitly selected optical exports."""

import argparse
import csv
from itertools import cycle
from math import isclose
from pathlib import Path
import re
import runpy
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plotting"))
import plot


def set_metric_limits(ax, metric, scale):
    ax.set_yscale(scale)
    if metric in plot.POSITION_METRICS:
        ax.set_ylim(0, 256)
    elif scale == "linear" and metric != "B_O_norm":
        ax.set_ylim(bottom=0)


def streaming_label(label):
    label = re.sub(r"^pressure-pass-(\d+)", r"Pass \1", label)
    label = re.sub(r"^voltage-run-(\d+)-11-26", r"\1 Nov", label)
    return label.replace(" (", "\n(")


def streaming_and_physics(rows, metrics, output, footnote=None):
    groups = {}
    for row in rows:
        groups.setdefault(row["dataset"], []).append(row)
    colors = dict(zip(sorted(groups, key=plot.natural_key), cycle(plot.COLORS)))
    for folder in ("streaming", "physics"):
        (output / folder).mkdir()
    run_positions = {(row["dataset"], row["run"]): index for index, row in enumerate(rows)}

    for metric in metrics:
        for scale in (("linear", "log") if metric in ("optical", "v50") else ("linear",)):
            fig, ax = plot.plt.subplots(figsize=(max(9, 1.4 * len(groups)), 5.5), layout="constrained")
            ticks, labels = [], []
            for label, group in groups.items():
                positions = [run_positions[label, row["run"]] for row in group]
                points, _ = plot.points(group, metric, lambda row: run_positions[label, row["run"]], scale)
                plot.draw(ax, points, colors[label], group[0]["kind"])
                ax.axvline(positions[0] - .5, color=".82", linewidth=.7)
                ticks.append((positions[0] + positions[-1]) / 2)
                labels.append(streaming_label(label))
            ax.set(xticks=ticks, xticklabels=labels, xlim=(-.5, len(rows) - .5),
                   xlabel="Run order within each dataset", ylabel=plot.YLABEL[metric])
            ax.tick_params(axis="x", labelsize=8)
            ax.grid(axis="y", alpha=.2)
            set_metric_limits(ax, metric, scale)
            plot.add_figure_footnote(fig, footnote)
            fig.savefig(output / "streaming" / f"{metric}_streaming_{scale}.png", dpi=150)
            plot.plt.close(fig)

            columns = min(3, len(groups))
            panels = (len(groups) + columns - 1) // columns
            fig, axes = plot.plt.subplots(panels, columns, squeeze=False, sharex=True, sharey=True,
                                         figsize=(4.2 * columns, 3.2 * panels), layout="constrained")
            axes.flat[0].set_yscale(scale)
            for ax, (label, group) in zip(axes.flat, groups.items()):
                points, _ = plot.points(group, metric, lambda row: row.get("v_over_p"), scale)
                plot.draw(ax, points, colors[label], group[0]["kind"])
                if not points:
                    ax.text(.5, .5, "No saved values", transform=ax.transAxes, ha="center", color=".4")
                ax.set_title(label, fontsize=9)
                ax.grid(alpha=.2)
            for ax in list(axes.flat)[len(groups):]:
                ax.set_visible(False)
            set_metric_limits(axes.flat[0], metric, scale)
            fig.supxlabel(plot.VP_LABEL)
            fig.supylabel(plot.YLABEL[metric])
            plot.add_figure_footnote(fig, footnote)
            fig.savefig(output / "physics" / f"{metric}_physics_{scale}.png", dpi=150)
            plot.plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", action="append", default=[], metavar="PATH",
                        help="results.csv or its plots folder; repeat for each dataset")
    parser.add_argument("--series", nargs=2, action="append", default=[],
                        metavar=("LABEL", "PATH"), help="legend label and results.csv or its plots folder")
    parser.add_argument("-o", "--output", type=Path, required=True,
                        help="new or empty comparison output folder")
    parser.add_argument("--paper-image", type=Path, default=plot.REFERENCE / "figure26_reference.png",
                        help="calibrated Figure 26 image; existing markers remain visible")
    parser.add_argument("--no-paper", action="store_true", help="skip the Figure 26 overlay")
    parser.add_argument("--spo", action=argparse.BooleanOptionalAction, default=True,
                        help="generate combined streaming and panelled physics plots (default: on)")
    parser.add_argument("--historical-charge", action="store_true",
                        help="fill missing V50 and optical/V50 from matching runs in reference/history.csv")
    parser.add_argument("--exclude-runs", default="", help="comma-separated run IDs to omit from all plots")
    parser.add_argument("--compact-labels", action="store_true",
                        help="mark recovered before-cut and saved fits with an asterisk and footnote")
    args = parser.parse_args()
    if not (args.input or args.series):
        parser.error("provide at least one -i PATH or --series LABEL PATH")
    output = args.output.expanduser()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error(f"output must be a new or empty directory: {output}")

    rows, sources, notes, labels = [], [], [], set()
    excluded = {run.strip() for run in args.exclude_runs.split(",") if run.strip()}
    omitted, before_cut, saved_fit = set(), [], []
    metrics = ("optical", "v50", "ratio", *plot.OPTIONAL_METRICS)
    history = {}
    if args.historical_charge:
        history = {(row["dataset"], row["run"]): row for row in
                   plot.load_results(plot.REFERENCE / "history.csv")}
    for label, name in [*((None, name) for name in args.input), *args.series]:
        path = Path(name).expanduser().resolve()
        if path.is_dir():
            path /= "results.csv"
        if not path.is_file():
            parser.error(f"results CSV not found: {path}")
        input_rows = plot.load_results(path)
        selected = [row for row in input_rows if not row["excluded"] and row["run"] not in excluded]
        if label is None:
            datasets = {row["dataset"] for row in selected}
            if len(datasets) != 1 or "" in datasets:
                parser.error(f"could not select one dataset name from {path}; use --series LABEL PATH")
            label = next(iter(datasets))
            for folder, phase in (("recovered-before", "before cut"),
                                  ("recovered-after", "after cut"),
                                  ("recovered-saved", "saved fit")):
                if folder in path.parts:
                    if args.compact_labels:
                        if phase in ("before cut", "saved fit"):
                            (before_cut if phase == "before cut" else saved_fit).append(label)
                            label += "*"
                    else:
                        label = f"{label} ({phase})"
                    break
        if label in labels:
            parser.error(f"duplicate series label: {label}; use --series with distinct labels")
        labels.add(label)
        for row in input_rows:
            if row["excluded"]:
                notes.append((label, row["run"], "excluded", "Excluded in the selected results.csv"))
                continue
            if row["run"] in excluded:
                omitted.add(row["run"])
                notes.append((label, row["run"], "excluded", "Omitted with --exclude-runs"))
                continue
            previous = history.get((row["dataset"], row["run"]))
            if previous and None not in (row["v_over_p"], previous["v_over_p"]) and isclose(
                row["v_over_p"], previous["v_over_p"], rel_tol=1e-6
            ):
                for metric in ("v50", "ratio"):
                    if row[metric] is None and previous[metric] is not None:
                        for key in (metric, f"{metric}_err", "v50_flags"):
                            row[key] = previous[key]
                        notes.append((label, row["run"], "historical charge",
                                      f"{metric} from reference/history.csv"))
            row["dataset"] = label
            for key in ("optical_flags", "v50_flags"):
                if row[key]:
                    notes.append((label, row["run"], "review flag", row[key]))
        if not any(row.get("v_over_p") is not None and any(row.get(metric) is not None for metric in metrics)
                   for row in selected):
            parser.error(f"no usable optical points for {label} in {path}")
        rows.extend(sorted(selected, key=lambda row: plot.natural_key(row["run"])))
        sources.append(dict(series=label, results_csv=str(path), run_rows=len(selected)))

    paper = None if args.no_paper else args.paper_image.expanduser()
    if paper is not None and not paper.is_file():
        parser.error(f"paper image not found: {paper}")
    metrics = [metric for metric in metrics if any(
        row.get(metric) is not None and row.get("v_over_p") is not None for row in rows
    )]
    warnings = []
    for metric in ("v50", "ratio"):
        if metric not in metrics:
            warnings.append(f"{metric}: no matching data in the selected exports")
    footnote_lines = []
    if before_cut or saved_fit:
        phases = []
        if before_cut:
            phases.append(f'{", ".join(before_cut)} uses before-cut fits.')
        if saved_fit:
            phases.append(f'{", ".join(saved_fit)} use saved fits with unverified spark-cut status.')
        footnote_lines.append("* " + " ".join(phases))
    if omitted:
        footnote_lines.append(f'Omitted runs: {", ".join(sorted(omitted, key=plot.natural_key))}.')
    footnote = "\n".join(footnote_lines) or None
    plot.comparison_plots(rows, output, paper, warnings, notes, metrics=metrics, footnote=footnote)
    organiser = runpy.run_path(str(REPO / "scripts" / "organise-optical-plots.py"))
    organiser["add_plot_ids"](output, "C", organiser["COMPARISON_PLOT_ORDER"])
    if args.spo:
        streaming_and_physics(rows, metrics, output, footnote=footnote)
        for folder in ("streaming", "physics"):
            organiser["add_plot_ids"](output / folder, "S", organiser["SUMMARY_PLOT_ORDER"])
    plot.write_csv(output / "sources.csv", sources, ("series", "results_csv", "run_rows"))
    with (output / "notes.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("series", "run", "category", "detail"))
        writer.writerows(notes)
    (output / "warnings.txt").write_text("\n".join(warnings) + "\n" if warnings else "No warnings.\n")
    print(f"Comparisons: {output}")


if __name__ == "__main__":
    main()
