"""Identify and optionally exclude candidate optical discharges by hit rate."""

from pathlib import Path
import os

import numpy as np
from scipy.ndimage import median_filter


def spark_cut(toa, report_path):
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
    if count:
        if mode == "off":
            duration = (int(toa[-1]) - int(toa[0])) / 1e13
        else:
            seconds = (toa - toa.min()) / 1e13
            duration = float(seconds.max())
            bins = (seconds / width).astype(np.intp)
            hits = np.bincount(bins)
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
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
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
