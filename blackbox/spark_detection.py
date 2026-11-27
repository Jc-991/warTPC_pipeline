"""Count and optionally exclude individual ToT outliers."""

import csv
from pathlib import Path
import os

import numpy as np


TOT_CUT_RMS = 10
TOA_TICKS_PER_SECOND = 10_000_000_000_000
GROUPED_SPARK_WIDTH_TICKS = 5 * (TOA_TICKS_PER_SECOND // 1000)  # 5 ms of detector time


def elapsed_toa(toa):
    """Return signed ticks relative to the first stored hit."""
    return toa.astype(np.int64) - np.int64(toa[0])


def veto_padding(before=None, after=None):
    """Return (before, after) veto padding in seconds; env vars default to 0."""
    values = []
    for value, name in ((before, "WARTPC_SPARK_VETO_BEFORE_S"), (after, "WARTPC_SPARK_VETO_AFTER_S")):
        if value is None:
            value = float(os.environ.get(name, "0") or 0)
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a non-negative number of seconds")
        values.append(float(value))
    return tuple(values)


def padded_intervals(intervals, before_ticks, after_ticks):
    """Pad each [start, stop) interval and merge overlaps (no clipping to the run)."""
    merged = []
    for start, stop in sorted((a - before_ticks, b + after_ticks) for a, b in intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], stop)
        else:
            merged.append([start, stop])
    return [tuple(interval) for interval in merged]


def group_tot(elapsed, tot, width):
    bins, inverse, counts = np.unique(elapsed // width, return_inverse=True, return_counts=True)
    return bins, inverse, counts, np.bincount(inverse, weights=tot)


def plot_statistics(values, lower=None, upper=None, quantity=None):
    values = np.asarray(values)
    label = f" ({quantity})" if quantity else ""
    underflow = np.count_nonzero(values < lower) if lower is not None else 0
    overflow = np.count_nonzero(values > upper) if upper is not None else 0
    return (
        f"Entries = {values.size:,}",
        f"Mean{label} = {np.mean(values):.4g}",
        f"RMS{label} = {np.std(values):.4g}",
        f"Underflow = {underflow:,}",
        f"Overflow = {overflow:,}",
    )


def draw_plot_statistics(ax, lines, *, x=0.02, y=0.97):
    ax.text(x, y, "\n".join(lines), transform=ax.transAxes, va="top", fontsize=8,
            bbox=dict(facecolor="white", edgecolor=".5", alpha=0.92))


def flag_sparks(tot):
    """Flag each hit strictly above the all-hit ToT cut."""
    cutoff = float(np.mean(tot) + TOT_CUT_RMS * np.std(tot)) if len(tot) else None
    return cutoff, tot > cutoff if cutoff is not None else np.zeros(0, dtype=bool)


def save_tot_distribution(tot, output, removed=None, *, grouped=False):
    """Plot individual or time-grouped ToT values with the cut marked."""
    from matplotlib import pyplot as plt

    counts, edges = np.histogram(tot, bins=128)
    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
    try:
        mean = float(np.mean(tot))
        rms = float(np.std(tot))
        lower, upper = mean - 5 * rms, mean + 5 * rms
        unit = "time bins" if grouped else "hits"
        if removed is None:
            ax.stairs(counts, edges, fill=True, color="tab:blue", label="All hits before tagging")
        else:
            removed_counts, _ = np.histogram(tot[removed], bins=edges)
            kept_counts = counts - removed_counts
            ax.stairs(kept_counts, edges, fill=True, color="tab:blue",
                      label=f"Kept ({int((~removed).sum()):,} {unit})")
            ax.stairs(counts, edges, baseline=kept_counts, fill=True, color="tab:red",
                      label=f"Removed ({int(removed.sum()):,} {unit})")
        ax.axvline(lower, color="black", linestyle="--", label=f"Mean − 5 RMS ({lower:.1f})")
        ax.axvline(upper, color="black", linestyle=":", label=f"Mean + 5 RMS ({upper:.1f})")
        cutoff = mean + TOT_CUT_RMS * rms
        ax.axvline(cutoff, color="tab:red", linestyle="--", label=f"ToT cut ({cutoff:.1f})")
        left, right = min(edges[0], lower), max(edges[-1], cutoff)
        padding = 0.02 * (right - left)
        ax.set(
            xlabel="Summed ToT per occupied time bin (stored units)" if grouped else "Hit ToT (stored units)",
            ylabel="Occupied time bins per histogram bin" if grouped else "Hits per bin",
            xlim=(left - padding, right + padding), yscale="log",
            title="Grouped ToT distribution and spark cut" if grouped else "Hit ToT distribution and spark cut",
        )
        ax.legend()
        draw_plot_statistics(ax, plot_statistics(tot, edges[0], edges[-1], "ToT"))
        fig.savefig(output, dpi=170)
    finally:
        plt.close(fig)


def save_tot_spectrum(seconds, tot, width, output, removed=None, *, spark_times=None):
    """Plot the unfiltered ToT distribution as a function of run time."""
    from matplotlib import pyplot as plt
    from matplotlib.colors import LogNorm

    lower = min(0, int(np.floor(seconds.min() / width)))
    upper = max(0, int(np.floor(seconds.max() / width))) + 1
    edges = np.arange(lower, upper + 1) * width
    counts, _, tot_edges = np.histogram2d(seconds, tot, bins=(edges, 128))
    # A full run has far more time columns than the image has pixels, and
    # drawing them directly drops most columns (a single 5 ms spark can vanish).
    # Show the largest bin of each group of columns per pixel instead.
    max_columns = 1600
    group = max(1, -(-counts.shape[0] // max_columns))
    if group > 1:
        padded = np.zeros((-(-counts.shape[0] // group) * group, counts.shape[1]))
        padded[:counts.shape[0]] = counts
        shown = padded.reshape(-1, group, counts.shape[1]).max(axis=1)
        right = edges[0] + shown.shape[0] * group * width
    else:
        shown, right = counts, edges[-1]
    label = f"Hits per {width * 1000:g} ms bin"
    if group > 1:
        label += f"\n(largest of every {group} bins)"
    fig, ax = plt.subplots(figsize=(12, 4), layout="constrained")
    try:
        image = ax.imshow(
            shown.T, origin="lower", aspect="auto", interpolation="nearest",
            extent=(edges[0], right, tot_edges[0], tot_edges[-1]),
            norm=LogNorm(vmin=1, vmax=max(2, shown.max())),
        )
        ax.set_xlim(edges[0], edges[-1])
        fig.colorbar(image, ax=ax, label=label)
        ax.set(xlabel="Time relative to first stored hit (s)", ylabel="Hit ToT (stored units)",
               title="ToT versus arrival time before spark tagging")
        if removed is not None:
            ax.scatter(seconds[removed], tot[removed], s=24, facecolors="none",
                       edgecolors="tab:red", linewidths=0.8,
                       label=f"Removed hits ({int(removed.sum()):,})")
            ax.set_title("ToT versus arrival time with removed hits marked")
            ax.legend(loc="upper right")
        if spark_times is not None:
            ax.set_title(f"ToT versus arrival time · {len(spark_times):,} flagged spark windows")
            # Use a visible line for each window because 5 ms is subpixel at full-run scale.
            for time in spark_times:
                ax.axvline(time, color="tab:red", linestyle="--", linewidth=1, alpha=0.85)
            if len(spark_times) <= 10 and np.all(np.diff(spark_times) > 0.025 * (edges[-1] - edges[0])):
                for index, time in enumerate(spark_times, 1):
                    ax.annotate(str(index), (time, 1), xycoords=ax.get_xaxis_transform(),
                                xytext=(0, 2), textcoords="offset points", ha="center",
                                va="bottom", color="tab:red", fontsize=8)
        max_tot = float(np.max(tot))
        ax.set_ylim(top=1.1 * max_tot if max_tot > 0 else tot_edges[-1])
        lines = plot_statistics(tot, tot_edges[0], tot_edges[-1], "ToT")
        draw_plot_statistics(ax, (*lines, f"Mean time (s) = {np.mean(seconds):.4g}",
                                  f"RMS time (s) = {np.std(seconds):.4g}"))
        fig.savefig(output, dpi=170)
    finally:
        plt.close(fig)


def spark_cut(toa, tot, report_path, *, mode=None, veto_before=None, veto_after=None):
    """Return the optional keep mask, original exposure, and excluded seconds.

    In grouped remove mode, veto_before/veto_after (seconds, default from
    WARTPC_SPARK_VETO_BEFORE_S / WARTPC_SPARK_VETO_AFTER_S, else 0) widen each
    flagged window to [start - before, stop + after); overlapping vetoes merge.
    """
    veto_before, veto_after = veto_padding(veto_before, veto_after)
    padded = veto_before > 0 or veto_after > 0
    vetoes = []
    if mode is None:
        mode = os.environ.get("WARTPC_SPARK_MODE", "off").strip().lower()
    if mode not in ("off", "detect", "remove"):
        raise ValueError("WARTPC_SPARK_MODE must be off, detect, or remove")

    method = os.environ.get("WARTPC_SPARK_METHOD", "hit")
    if method not in ("hit", "grouped"):
        raise ValueError("WARTPC_SPARK_METHOD must be hit or grouped")
    grouped = method == "grouped"
    # Time columns of the ToT-versus-time image: the same 5 ms as the spark grouping.
    width = GROUPED_SPARK_WIDTH_TICKS / TOA_TICKS_PER_SECOND
    count = len(toa)
    duration = excluded = 0.0
    intervals = []
    values = tot
    cutoff = None
    flagged = np.zeros(0, dtype=bool)
    keep = None
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    if count:
        span = int(toa[-1]) - int(toa[0])
        if span < 0:
            raise ValueError("Last stored ToA precedes first stored ToA; invalid exposure")
        duration = span / TOA_TICKS_PER_SECOND
        if mode != "off":
            elapsed = elapsed_toa(toa)
            seconds = elapsed / TOA_TICKS_PER_SECOND
            save_tot_spectrum(seconds, tot, width,
                              report.with_name("tot-vs-time-before-sparks.png"))
            if grouped:
                bins, inverse, _, values = group_tot(elapsed, tot, GROUPED_SPARK_WIDTH_TICKS)
                cutoff, flagged = flag_sparks(values)
                intervals = [
                    (int(bin_id) * GROUPED_SPARK_WIDTH_TICKS,
                     (int(bin_id) + 1) * GROUPED_SPARK_WIDTH_TICKS)
                    for bin_id in bins[flagged]
                ]
                if mode == "remove" and intervals:
                    if padded:
                        vetoes = padded_intervals(
                            intervals,
                            int(round(veto_before * TOA_TICKS_PER_SECOND)),
                            int(round(veto_after * TOA_TICKS_PER_SECOND)))
                        starts = np.array([start for start, _ in vetoes], dtype=np.int64)
                        stops = np.array([stop for _, stop in vetoes], dtype=np.int64)
                        # Index of the last veto starting at or before each hit.
                        index = np.searchsorted(starts, elapsed, side="right") - 1
                        inside = (index >= 0) & (elapsed < stops[np.maximum(index, 0)])
                        keep = ~inside
                    else:
                        keep = ~flagged[inverse]
                    excluded_ticks = sum(max(0, min(stop, span) - max(0, start))
                                         for start, stop in (vetoes if padded else intervals))
                    excluded = excluded_ticks / TOA_TICKS_PER_SECOND
            else:
                cutoff, flagged = flag_sparks(values)
                if mode == "remove" and flagged.any():
                    keep = ~flagged
        elif not grouped:
            cutoff, flagged = flag_sparks(values)

    remaining = int(keep.sum()) if keep is not None else count
    removed = count - remaining
    usable = duration - excluded
    rejected = mode == "remove" and (remaining == 0 or usable <= 0)
    if rejected:
        status = "rejected: no hits or usable exposure would remain"
    elif removed:
        status = "yes"
    elif mode == "remove":
        status = "no (no entries above the ToT cut)"
    else:
        status = f"no ({mode} mode)"
    sparks = int(flagged.sum())
    lines = [
        f"Mode: {mode}",
        f"Removal applied: {status}",
        f"Spark count: {sparks}",
        f"Spark algorithm iterations: {int(mode != 'off' and cutoff is not None)}",
        f"Candidate intervals: {len(intervals)}",
        f"Hits before/kept: {count} / {remaining}",
        f"Hits excluded: {removed}",
        f"Exposure before/after (s): {duration:.9g} / {usable:.9g}",
        f"Exposure excluded (s): {excluded:.9g}",
    ]
    if grouped:
        lines.extend((
            f"Spark count rule: occupied time bins with summed ToT > mean + {TOT_CUT_RMS} RMS",
            f"Grouping width (s): {GROUPED_SPARK_WIDTH_TICKS / TOA_TICKS_PER_SECOND:g}",
        ))
        if padded:
            lines.extend((
                f"Veto before/after each flagged window (s): {veto_before:g} / {veto_after:g}",
                f"Merged veto intervals: {len(vetoes)}",
            ))
        for start, stop in intervals:
            lines.append(f"Candidate since first hit (s): "
                         f"{start / TOA_TICKS_PER_SECOND:.13f} to {stop / TOA_TICKS_PER_SECOND:.13f}")
        for start, stop in vetoes:
            lines.append(f"Veto since first hit (s): "
                         f"{start / TOA_TICKS_PER_SECOND:.13f} to {stop / TOA_TICKS_PER_SECOND:.13f}")
    else:
        lines.append(f"Spark count rule: individual hits with ToT > mean + {TOT_CUT_RMS} RMS")
    if cutoff is not None:
        lines.append(f"ToT cut (strictly greater than): {cutoff:.9g}")
        label = "Time bins above ToT cut" if grouped else "Hits above ToT cut"
        lines.append(f"{label}: {sparks}")
    report.write_text("\n".join(lines) + "\n")
    print(f"Spark mode: {mode}; spark count: {sparks}; removal applied: {status}; report: {report}", flush=True)
    if rejected:
        raise ValueError(f"Spark cut rejected; see {report}")
    if count and mode != "off":
        removed_mask = None
        if mode == "remove":
            removed_mask = ~keep if keep is not None else np.zeros(count, dtype=bool)
            save_tot_spectrum(seconds, tot, width,
                              report.with_name("tot-vs-time-spark-removal.png"),
                              removed=removed_mask,
                              spark_times=[(start + stop) / (2 * TOA_TICKS_PER_SECOND)
                                           for start, stop in intervals] if grouped else None)
        histogram_mask = flagged if mode == "remove" else None
        save_tot_distribution(values, report.with_name("tot-distribution-before-sparks.png"),
                              histogram_mask, grouped=grouped)
    return keep, duration, excluded


if __name__ == "__main__":
    import argparse
    import h5py
    import sys

    parser = argparse.ArgumentParser(description="Count high-ToT sparks in saved optical runs.")
    parser.add_argument("--fallback-optical", type=Path,
                        help="try <dir>/<run>/output.hdf5 when a primary file is unreadable")
    parser.add_argument("--csv", type=Path, help="write counts to this CSV")
    parser.add_argument("--removal-plots", type=Path,
                        help="save plots and the ToT cut report for one HDF5 file to this directory")
    parser.add_argument("hdf5", type=Path, nargs="+")
    args = parser.parse_args()
    if args.removal_plots is not None and len(args.hdf5) != 1:
        parser.error("--removal-plots requires exactly one HDF5 file")
    failed = False
    rows = []
    for path in args.hdf5:
        run = path.parent.name
        sources = [path]
        if args.fallback_optical is not None:
            sources.append(args.fallback_optical / run / "output.hdf5")
        for index, source_path in enumerate(sources):
            try:
                with h5py.File(source_path, "r") as source:
                    hits = source["PixelHits"]
                    toa, tot = hits["toa"][:], hits["tot"][:]
                    _, flagged = flag_sparks(tot)
                    count = int(flagged.sum())
            except (OSError, KeyError, ValueError) as error:
                print(f"{run}: cannot read {source_path}: {error}", file=sys.stderr, flush=True)
                continue
            suffix = " (before-pass HDF5)" if index else ""
            if args.removal_plots is not None:
                from matplotlib import use

                use("Agg")
                spark_cut(toa, tot, args.removal_plots / "spark_status.txt", mode="remove")
            print(f"{run}: {count}{suffix}", flush=True)
            rows.append((run, count))
            break
        else:
            failed = True
            print(f"{run}: spark count unavailable", flush=True)
            rows.append((run, ""))
    if args.csv is not None:
        with args.csv.open("w", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(("run", "spark_count"))
            writer.writerows(rows)
    sys.exit(int(failed))
