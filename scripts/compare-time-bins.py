#!/usr/bin/env python3
"""Compare fixed-width ToA grouping using the original hits from an optical run."""

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blackbox"))
from spark_detection import flag_sparks, group_tot, save_tot_distribution


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
    bins, _, counts, summed_tot = group_tot(elapsed, tot, width)
    return bins, counts, summed_tot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hdf5", type=Path, help="optical run's output.hdf5")
    parser.add_argument("-o", "--output", type=Path, required=True, help="comparison PNG")
    parser.add_argument("--bins-ms", nargs="+", type=bin_width,
                        default=[bin_width(w) for w in ("1", "0.1", "0.05", "0.02", "0.01", "0.005")])
    parser.add_argument("--cut-histogram", action="store_true",
                        help="plot the grouped ToT histogram and its cut for one bin width")
    args = parser.parse_args()
    if args.cut_histogram and len(args.bins_ms) != 1:
        parser.error("--cut-histogram requires one --bins-ms value")

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
    if args.cut_histogram:
        _, counts, sums = group_hits(elapsed, tot, args.bins_ms[0])
        cutoff, flagged = flag_sparks(sums)
        save_tot_distribution(sums, args.output, flagged, grouped=True)
        print(f"{toa.size:,} hits, {counts.size:,} occupied time bins, "
              f"{flagged.sum():,} above grouped ToT cut ({cutoff:.6g})")
        return

    ref_bins, ref_counts, _ = group_hits(elapsed, tot, TICKS_PER_MS)
    burst_start = int(ref_bins[ref_counts.argmax()]) * TICKS_PER_MS
    burst_end = burst_start + TICKS_PER_MS
    margin = 2 * TICKS_PER_MS
    left = max(0, burst_start - margin)
    right = burst_end + margin

    comparisons = [group_hits(elapsed, tot, width) for width in args.bins_ms]
    lower = min(summed_tot.min() for _, _, summed_tot in comparisons)
    upper = max(summed_tot.max() for _, _, summed_tot in comparisons)
    histogram_edges = np.histogram_bin_edges([lower, upper], bins=100)

    fig, axes = plt.subplots(len(args.bins_ms), 2, squeeze=False,
                             figsize=(12, 2.8 * len(args.bins_ms)), sharex="col", layout="constrained")
    fig.suptitle(f"{args.hdf5.parent.name} · {toa.size:,} hits before spark removal")
    print("width_ms,occupied_bins,multi_hit_bins,peak_hits,peak_start_ms")
    for width, (histogram, timeline), (bins, counts, summed_tot) in zip(
        args.bins_ms, axes, comparisons
    ):
        starts = bins * width
        peak = int(counts.argmax())
        width_ms = width / TICKS_PER_MS
        print(f"{width_ms:g},{bins.size},{np.count_nonzero(counts > 1)},"
              f"{counts[peak]},{starts[peak] / TICKS_PER_MS:.10f}")

        histogram.hist(summed_tot, bins=histogram_edges, log=True)
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
