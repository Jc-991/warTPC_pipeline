#!/usr/bin/env python3
"""Compare fixed-width ToA grouping using the original hits from an optical run."""

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np


TICKS_PER_MS = 10_000_000_000


def bin_width(value):
    try:
        ticks = Decimal(value) * TICKS_PER_MS
        if ticks.is_finite() and 1 <= ticks <= np.iinfo(np.int64).max and ticks == int(ticks):
            return int(ticks)
    except InvalidOperation:
        pass
    raise argparse.ArgumentTypeError("bin width must be positive and a whole number of ToA ticks")


def group_hits(elapsed, tot, width):
    bins, inverse, counts = np.unique(elapsed // width, return_inverse=True, return_counts=True)
    return bins, counts, np.bincount(inverse, weights=tot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hdf5", type=Path, help="optical run's output.hdf5")
    parser.add_argument("-o", "--output", type=Path, required=True, help="comparison PNG")
    parser.add_argument("--bins-ms", nargs="+", type=bin_width,
                        default=[bin_width(w) for w in ("1", "0.5", "0.2", "0.1", "0.05")])
    args = parser.parse_args()

    import h5py
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    with h5py.File(args.hdf5, "r") as source:
        hits = source["PixelHits"]
        toa, tot = hits["toa"][:], hits["tot"][:]
    if toa.size == 0:
        parser.error("the input contains no hits")

    elapsed = toa - toa.min()
    ref_bins, ref_counts, _ = group_hits(elapsed, tot, TICKS_PER_MS)
    burst_start = int(ref_bins[ref_counts.argmax()]) * TICKS_PER_MS
    burst_end = burst_start + TICKS_PER_MS
    margin = 2 * TICKS_PER_MS
    left = max(0, burst_start - margin)
    right = burst_end + margin

    fig, axes = plt.subplots(len(args.bins_ms), 2, squeeze=False,
                             figsize=(12, 2.8 * len(args.bins_ms)), layout="constrained")
    fig.suptitle(f"{args.hdf5.parent.name} · {toa.size:,} hits before spark removal")
    print("width_ms,occupied_bins,multi_hit_bins,peak_hits,peak_start_ms")
    for width, (histogram, timeline) in zip(args.bins_ms, axes):
        bins, counts, summed_tot = group_hits(elapsed, tot, width)
        starts = bins * width
        peak = int(counts.argmax())
        width_ms = width / TICKS_PER_MS
        print(f"{width_ms:g},{bins.size},{np.count_nonzero(counts > 1)},"
              f"{counts[peak]},{starts[peak] / TICKS_PER_MS:.10f}")

        histogram.hist(summed_tot, bins=100, log=True)
        histogram.set(title=f"{width_ms:g} ms · {bins.size:,} occupied bins",
                      xlabel="Summed ToT per bin (stored units)", ylabel="Occupied bins")

        visible = (starts < right) & (starts + width > left)
        timeline.bar(starts[visible] / TICKS_PER_MS, counts[visible],
                     width=width_ms, align="edge")
        timeline.axvspan(burst_start / TICKS_PER_MS, burst_end / TICKS_PER_MS,
                         color="tab:orange", alpha=0.18)
        timeline.set(xlim=(left / TICKS_PER_MS, right / TICKS_PER_MS),
                     xlabel="Time since first hit (ms)", ylabel="Hits per bin",
                     title="Around the busiest 1 ms interval")
        timeline.ticklabel_format(axis="x", style="plain", useOffset=False)

    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
