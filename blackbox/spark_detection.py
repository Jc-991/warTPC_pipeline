"""Identify and optionally exclude candidate optical discharges by hit rate."""

from pathlib import Path
import os

import numpy as np
from scipy.ndimage import median_filter


def save_tot_spectrum(seconds, tot, time_bins, width, output):
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
        fig.savefig(output, dpi=170)
    finally:
        plt.close(fig)


def spark_cut(toa, tot, report_path):
    """Return the optional keep mask, original exposure, and excluded seconds."""
    mode = os.environ.get("WARTPC_SPARK_MODE", "off").strip().lower()
    if mode not in ("off", "detect", "remove"):
        raise ValueError("WARTPC_SPARK_MODE must be off, detect, or remove")

    width = 0.01
    recovery = 0.05
    count = len(toa)
    duration = 0.0
    intervals = []
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
            hits = np.bincount(bins)
            save_tot_spectrum(seconds, tot, len(hits), width,
                              report.with_name("tot-vs-time-before-sparks.png"))
            baseline = median_filter(hits, size=101, mode="reflect")
            threshold = np.maximum.reduce((
                np.full(len(hits), 30.0),
                3.0 * baseline,
                baseline + 8.0 * np.sqrt(np.maximum(baseline, 1)),
            ))
            for index in np.flatnonzero(hits >= threshold):
                start = max(0.0, (index - 1) * width)
                stop = min(np.nextafter(duration, np.inf), (index + 1) * width + recovery)
                if intervals and start <= intervals[-1][1]:
                    intervals[-1] = (intervals[-1][0], stop)
                else:
                    intervals.append((start, stop))
            if mode == "remove" and intervals:
                starts, stops = np.asarray(intervals).T
                # Inside an interval when one more start than stop has passed.
                keep = np.searchsorted(starts, seconds, side="right") == np.searchsorted(
                    stops, seconds, side="right"
                )

    excluded = sum(min(stop, duration) - start for start, stop in intervals) if keep is not None else 0.0
    remaining = int(keep.sum()) if keep is not None else count
    removed = count - remaining
    usable = duration - excluded
    rejected = mode == "remove" and (remaining == 0 or usable <= 0)
    if rejected:
        status = "rejected: no hits or usable exposure would remain"
    elif removed:
        status = "yes"
    elif mode == "remove":
        status = "no (no candidate intervals)"
    else:
        status = f"no ({mode} mode)"
    lines = [
        f"Mode: {mode}",
        f"Removal applied: {status}",
        f"Candidate intervals: {len(intervals)}",
        f"Hits before/kept: {count} / {remaining}",
        f"Hits excluded: {removed}",
        f"Exposure before/after (s): {duration:.9g} / {usable:.9g}",
        f"Exposure excluded (s): {excluded:.9g}",
    ]
    if mode != "off":
        lines.append("Detection: 10 ms bins, local median over 101 bins, 10 ms before and 50 ms after flagged bins")
        lines.extend(f"Candidate since first hit (s): {start:.9g} to {min(stop, duration):.9g}"
                     for start, stop in intervals)
    report.write_text("\n".join(lines) + "\n")
    print(f"Spark mode: {mode}; removal applied: {status}; report: {report}", flush=True)
    if rejected:
        raise ValueError(f"Spark cut rejected; see {report}")
    return keep, duration, excluded
