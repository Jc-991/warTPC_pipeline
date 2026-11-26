#!/usr/bin/env python3
"""Number PNGs inside each run folder in the final optical export."""

import argparse
from pathlib import Path


PLOT_ORDER = (
    "2D_integrated_ToT",
    "x_projection_signal",
    "y_projection_signal",
    "combined_integral_distribution",
    "tot-distribution-before-sparks",
    "tot-vs-time-before-sparks",
    "tot-vs-time-spark-removal",
    "X_mean_fit_distribution",
    "X_RMS_fit_distribution",
    "Y_mean_fit_distribution",
    "Y_RMS_fit_distribution",
    "B_O_norm_fit_distribution",
)


SUMMARY_PLOT_ORDER = (
    "optical_streaming_linear", "optical_physics_linear",
    "optical_streaming_log", "optical_physics_log",
    "X_mean_streaming_linear", "X_mean_physics_linear",
    "X_RMS_streaming_linear", "X_RMS_physics_linear",
    "Y_mean_streaming_linear", "Y_mean_physics_linear",
    "Y_RMS_streaming_linear", "Y_RMS_physics_linear",
    "B_X_norm_streaming_linear", "B_X_norm_physics_linear",
    "B_Y_norm_streaming_linear", "B_Y_norm_physics_linear",
    "number_of_sparks_streaming_linear", "number_of_sparks_physics_linear",
    "fraction_of_removed_exposure_streaming_linear",
    "fraction_of_removed_exposure_physics_linear",
    "v50_streaming_linear", "v50_physics_linear",
    "v50_streaming_log", "v50_physics_log",
    "ratio_streaming_linear", "ratio_physics_linear",
    "S_O_over_B_O_ratio_streaming_linear", "S_O_over_B_O_ratio_physics_linear",
    "B_O_norm_streaming_linear", "B_O_norm_physics_linear",
)
COMPARISON_PLOT_ORDER = (
    "optical_physics_comparison", "optical_paper_overlay",
    "v50_physics_comparison", "ratio_physics_comparison",
    "X_mean_overlay", "X_RMS_overlay", "Y_mean_overlay", "Y_RMS_overlay",
    "B_X_norm_overlay", "B_Y_norm_overlay", "number_of_sparks_overlay",
    "fraction_of_removed_exposure_overlay",
    "S_O_over_B_O_ratio_overlay", "B_O_norm_overlay",
)


def add_plot_ids(folder, prefix, stems):
    for number, stem in enumerate(stems, start=1):
        source = folder / f"{stem}.png"
        if source.is_file():
            target = folder / f"{prefix}{number:02d}_{source.name}"
            if target.exists():
                raise FileExistsError(f"Plot destination already exists: {target}")
            source.rename(target)


def plot_sort_key(stem):
    base, _, suffix = stem.rpartition("_")
    phase = {"before": 1, "after": 2}.get(suffix, 0)
    kind = base if phase else stem
    order = PLOT_ORDER.index(kind) if kind in PLOT_ORDER else len(PLOT_ORDER)
    return order, kind, phase, stem


def organise(root):
    moves = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        run = folder.name
        plots = []
        for source in (*folder.glob("*.png"), *root.glob(f"{run}_*.png")):
            stem = source.stem
            if stem.startswith(f"{run}_"):
                stem = stem[len(run) + 1:]
            prefix, _, remainder = stem.partition("_")
            if len(prefix) == 3 and prefix.isdigit() and remainder:
                stem = remainder
            plots.append((source, stem))
        plots.sort(key=lambda plot: plot_sort_key(plot[1]))
        for number, (source, stem) in enumerate(plots, start=1):
            target = folder / f"{number * 10:03d}_{stem}.png"
            if source != target:
                moves.append((source, target))

    targets = set()
    for _, target in moves:
        if target.exists() or target in targets:
            raise FileExistsError(f"Plot destination already exists: {target}")
        targets.add(target)
    for source, target in moves:
        source.rename(target)
    return len(moves)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--workflow-export", action="store_true",
                        help="number plots in the workflow's top-level plots folder")
    args = parser.parse_args()
    if args.workflow_export:
        add_plot_ids(args.directory / "summary_plots", "S", SUMMARY_PLOT_ORDER)
        add_plot_ids(args.directory / "comparisons", "S", SUMMARY_PLOT_ORDER)
        add_plot_ids(args.directory / "comparisons", "C", COMPARISON_PLOT_ORDER)
        directory = args.directory / "optical_per_run"
    else:
        directory = args.directory
    if directory.is_dir():
        print(f"Organised {organise(directory)} per-run plots")
