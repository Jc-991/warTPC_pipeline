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
    args = parser.parse_args()
    print(f"Organised {organise(args.directory)} per-run plots")
