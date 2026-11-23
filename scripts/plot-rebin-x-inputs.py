#!/usr/bin/env python3
"""Save the original and X-rebinned inputs to Matt's 2D Gaussian fit."""

import argparse
from pathlib import Path

import h5py
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def save_comparison(run, destination):
    with h5py.File(run / "output.hdf5", "r") as source:
        hits = source["PixelHits"]
        original = np.zeros((256, 256), dtype=np.int64)
        np.add.at(original, (hits["y"][:], hits["x"][:]), hits["tot"][:])

    rebinned = original[:, 0::2] + original[:, 1::2]
    fig, axes = plt.subplots(2, 3, figsize=(13, 8), layout="constrained")
    for row, (image, width, title) in enumerate(
        [(original, 1, "Original"), (rebinned, 2, "X rebinned by 2")]
    ):
        map_ax, x_ax, y_ax = axes[row]
        heatmap = map_ax.imshow(
            image, extent=(-0.5, 255.5, 255.5, -0.5),
            interpolation="nearest", vmin=0, vmax=rebinned.max(),
        )
        fig.colorbar(heatmap, ax=map_ax, label="Summed ToT per bin")
        map_ax.set(title=f"{title} · 2D ToT", xlabel="X pixel", ylabel="Y pixel")
        x_ax.stairs(image.sum(axis=0) / 1e6, np.arange(0, 257, width) - 0.5)
        y_ax.stairs(image.sum(axis=1) / 1e6, np.arange(257) - 0.5)
        x_ax.set(title="X projection", xlabel="X pixel")
        y_ax.set(title="Y projection", xlabel="Y pixel")
        for projection in (x_ax, y_ax):
            projection.set(xlim=(-0.5, 255.5), ylabel="Summed ToT per bin (× 10⁶)")
    for column in (1, 2):
        axes[1, column].sharey(axes[0, column])
        axes[1, column].relim()
        axes[1, column].autoscale_view(scalex=False)
    fig.suptitle(f"{run.name} · Before the 2D Gaussian fit")
    fig.savefig(destination / f"{run.name}-before-fit.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    runs = sorted((args.results / "optical").glob("*/output.hdf5"))
    if not runs:
        parser.error(f"No optical run HDF5 files found in {args.results}")

    args.output.mkdir()
    failures = 0
    for source in runs:
        try:
            save_comparison(source.parent, args.output)
            print(f"Saved {source.parent.name}", flush=True)
        except (OSError, ValueError, KeyError, IndexError) as error:
            print(f"{source.parent.name}: {error}", flush=True)
            failures += 1
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
