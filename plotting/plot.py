#!/usr/bin/env python3
"""Make the PLOT_GUIDE.md tables and plots from an `optical`/`charge` output folder.

    plot.py -i <result_dir> -o <plot_dir>

<result_dir> is what `optical -o` / `charge -o` wrote (an original dataset works
too): optical/<run>/integral.csv and images, charge/<run>/pulseheights.csv,
settings.csv in either. The input is only read.
"""
import argparse, csv, re, shutil, sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.signal import find_peaks, peak_widths
from run_summaries import write_combined_run_summary

REFERENCE = Path(__file__).resolve().parent.parent / 'reference'

# V50 method of charge_signal_1.ipynb, identical to pipeline/pipeline.py so the
# values stay comparable with reference/history.csv.
BINS = np.linspace(0, 6000, 200)
V50_METHOD = ('scipy find_peaks on a 199-bin 0-6000 mV histogram of channel-B pulse heights '
              '(first bin ignored; prominence 0.5, distance 15 bins); of the two tallest peaks the '
              'higher-mV one is taken, at its bin lower edge; candidates under 20 counts are set to 0 '
              '(no estimate); width = FWHM/2.355. No Gaussian fit.')

# The four standard files copied into optical_per_run/<run>/: source (inside
# optical/<run>/) -> name. All from the 4to8 setting with the 2nd-degree
# background fit, the same whether rebin-x is on or off. Everything else stays
# in optical/<run>/.
OPTICAL_PER_RUN = {
    'signal-integral_x/2nd_degree/4to8/ToT-image.png': '2D_integrated_ToT.png',
    'signal-integral_x/2nd_degree/4to8/4to8_signal.png': 'x_projection_signal.png',
    'signal-integral_y/2nd_degree/4to8/4to8_signal.png': 'y_projection_signal.png',
    'Total-Stacked-signal-integral.png': 'combined_integral_distribution.png',
}
# Failure notes written by optical-analysis.py; their first line goes into status.txt.
OPTICAL_FAILURE_NOTES = ('diagnostics/no_hits.txt', 'diagnostics/fit_failed.txt',
                         'diagnostics/sideband_failed.txt')

YLABEL = {'optical': r'$S_O^{\mathrm{norm}}$ (ms s$^{-1}$)',
          'v50': r'$V_{50}$ peak estimate (mV)',
          'ratio': r'$S_O^{\mathrm{norm}}/V_{50}$ (ms s$^{-1}$ mV$^{-1}$)',
          'number_of_sparks': 'Number of flagged spark windows',
          'fraction_of_removed_exposure': 'Exposure removed (absolute fraction, 1 = 100%)'}
PROJECTION_METRICS = {
    'X_mean': r'$X_{\mathrm{mean}}$ — mean position (pixels)',
    'X_RMS': r'$X_{\mathrm{RMS}}$ — positional RMS (pixels)',
    'Y_mean': r'$Y_{\mathrm{mean}}$ — mean position (pixels)',
    'Y_RMS': r'$Y_{\mathrm{RMS}}$ — positional RMS (pixels)',
    'B_O_norm': r'$B_O^{\mathrm{norm}}$ — background ToT per exposure (ms/s)',
}
POSITION_METRICS = ('X_mean', 'X_RMS', 'Y_mean', 'Y_RMS')
YLABEL.update(PROJECTION_METRICS)
YLABEL['S_O_over_B_O_ratio'] = r'$S_O/B_O$ (dimensionless)'
SPARK_METRICS = ('number_of_sparks', 'fraction_of_removed_exposure')
OPTIONAL_METRICS = (*SPARK_METRICS, "X_mean", "Y_mean", "B_O_norm", "S_O_over_B_O_ratio")
OPTICAL_RMS_FIELDS = ("X_mean_err", "Y_mean_err", "B_O_norm_err", "S_O_over_B_O_ratio_err")
VP_LABEL = r'$V_{43+21}/P$ (kV bar$^{-1}$)'
# PLOT_GUIDE: hollow squares for pressure runs, solid circles for voltage runs.
MARKER = {'pressure': ('s', False), 'voltage': ('o', True), 'unknown': ('D', True)}
COLORS = plt.rcParams['axes.prop_cycle'].by_key()['color']

# Paper Fig. 26 calibration (2750x2000 image): axis pixel positions and ranges.
PAPER_SIZE = (2750, 2000)
PAPER_X = (480, 2386, 0.0, 3.0)        # pixel at x=0, pixel at x=3, data range
PAPER_Y = (1616, 247, 1e-4, 100.0)     # pixel at 1e-4, pixel at 100 (log axis)


# ---------------------------------------------------------------- helpers
def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def first_row(path):
    with path.open(newline='') as f:
        for row in csv.reader(f):
            if row:
                return row
    raise ValueError(f'{path.name} is empty')


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


def infer_kind(dataset, runs=()):
    name = dataset.lower()
    if 'pressure' in name or name.startswith('prp'):
        return 'pressure'
    if 'voltage' in name or name.startswith('vr'):
        return 'voltage'
    runs = [r.lower() for r in runs]
    if runs and all(r.startswith('prp') for r in runs):
        return 'pressure'
    if runs and all(r.startswith('vr') for r in runs):
        return 'voltage'
    return 'unknown'


def write_csv(path, rows, fields):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in fields})


# ---------------------------------------------------------------- per-run analysis
def read_settings(path):
    row = first_row(path)
    if len(row) < 8:
        raise ValueError(f'{path} has {len(row)} columns, expected 8')
    out = {'settings_id': row[0].strip(), 'pressure_mbar': num(row[1]),
           'methane_fraction': num(row[7])}
    for i in range(5):
        out[f'V{i}'] = num(row[2 + i])
    p, v = out['pressure_mbar'], [out[f'V{i}'] for i in range(5)]
    if p and p > 0 and None not in v:
        out['v_over_p'] = (v[4] - v[3] + v[2] - v[1]) / p   # V/mbar == kV/bar
    return out


def v50_analysis(path, run, outdir):
    a = np.genfromtxt(path, skip_header=1, ndmin=2)
    if a.shape[1] < 3:
        raise ValueError('pulseheights.csv has fewer than 3 columns')
    values = a[:, 2]
    finite = values[np.isfinite(values)]
    if not len(finite):
        raise ValueError('no finite V50 values')
    h, _ = np.histogram(finite, bins=BINS)
    outside = int(((finite < 0) | (finite > 6000)).sum())
    candidate = h.copy()
    candidate[0] = 0
    peaks, _ = find_peaks(candidate, prominence=.5, distance=15)
    peaks = peaks[peaks > 0]
    top = peaks[np.argsort(h[peaks])[-2:]]
    peak = width = None
    flags = []
    if len(top) == 0:
        flags.append('no peak found after ignoring first bin')
    else:
        if len(top) == 1:
            flags.append('single-peak fallback')
        amps = h[top] - np.min(h)
        mus = np.where(amps < 20, 0., BINS[top])
        widths = peak_widths(candidate, top, rel_height=.5)[0] * np.mean(np.diff(BINS)) / 2.355
        k = int(np.argmax(mus))
        peak, width = float(mus[k]), float(widths[k])
        if top[k] == 1:
            flags.append('peak touches ignored first bin')
        if not np.isfinite(width) or width <= 0:
            width = None
            flags.append('peak width unavailable')
        if (amps < 20).any():
            flags.append('candidate peak below 20 counts')
        if peak <= 0:
            flags.append('no valid peak estimate (notebook assigns 0)')
    if outside:
        flags.append(f'{outside} events outside 0-6000 mV')
    valid = peak is not None and peak > 0

    # Display range adapts to the data; the estimate above always uses BINS.
    xmax = min(max(10., float(np.quantile(finite, .90)) * 1.3), max(8100., float(np.max(finite))))
    shown = int(((finite >= 0) & (finite <= xmax)).sum())
    nbins = min(80, max(20, int(np.sqrt(len(finite)))))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(finite, bins=np.linspace(0, xmax, nbins + 1), color='#247ca5', edgecolor='white', linewidth=.3)
    if valid:
        ax.axvline(peak, color='#c62828', lw=1.2, ls='--', label=f'V50 estimate {peak:.0f} mV')
        ax.legend(loc='upper left', fontsize=8)
    ax.set_xlim(0, xmax)
    ax.set_xlabel(r'Channel B $V_{50}$ (mV)')
    ax.set_ylabel('Entries')
    ax.set_title(f'{run} - V50 distribution')
    ax.text(.98, .97, f'Events: {len(finite):,}\nOutside shown range: {len(finite) - shown:,}\n'
            f'Bin width: {xmax / nbins:.0f} mV ({nbins} bins)',
            transform=ax.transAxes, ha='right', va='top', fontsize=9,
            bbox=dict(facecolor='white', edgecolor='0.8'))
    ax.grid(axis='y', alpha=.2)
    fig.tight_layout()
    fig.savefig(outdir / f'{run}_V50.png', dpi=150)
    plt.close(fig)
    return {'v50': peak if valid else None, 'v50_err': width if valid else None,
            'v50_entries': len(values), 'v50_nonfinite': len(values) - len(finite),
            'v50_outside_0_6000': outside, 'v50_flags': '; '.join(flags)}


def read_spark_summary(path):
    with path.open(newline='') as handle:
        return next(csv.DictReader(handle, delimiter='\t'))


def spark_values(summary):
    fraction = num(summary.get('fraction_of_removed_exposure'))
    if fraction is None:
        percent = num(summary.get('percentage_of_removed_exposure'))
        fraction = None if percent is None else percent / 100
    return dict(number_of_sparks=num(summary.get('number_of_sparks')),
                fraction_of_removed_exposure=fraction)


def projection_values(row):
    # Earlier exports used these four names for moments of ToT amplitudes.
    values = {
        "B_O_norm": num(row.get("B_O_norm_ms_per_s", row.get("B_O_norm"))),
        "B_O_norm_err": num(row.get("B_O_norm_RMS_ms_per_s", row.get("B_O_norm_err"))),
        "S_O_over_B_O_ratio": num(row.get("S_O_over_B_O_ratio")),
        "S_O_over_B_O_ratio_err": num(row.get("S_O_over_B_O_ratio_err")),
    }
    if 'X_mean_pixel' in row or row.get('projection_position_unit') == 'pixel':
        for axis in ('X', 'Y'):
            mean = f'{axis}_mean'
            rms = f'{axis}_RMS'
            values[mean] = num(row.get(f'{mean}_pixel', row.get(mean)))
            values[f'{mean}_err'] = num(row.get(f'{rms}_pixel', row.get(f'{mean}_err', row.get(rms))))
    return values


def add_fit_distribution_stats(ax, values, edges):
    entries = np.asarray(values)
    mean = np.mean(entries)
    rms = np.std(entries)
    relative = f'{100 * rms / abs(mean):.1f}%' if mean else 'N/A'
    lines = (
        f'Entries = {entries.size}',
        f'Mean = {mean:.4g}',
        f'RMS = {rms:.4g}',
        f'Percent = {relative}',
        f'Underflow = {np.count_nonzero(entries < edges[0])}',
        f'Overflow = {np.count_nonzero(entries > edges[-1])}',
    )
    ax.text(1.03, 0.98, '\n'.join(lines), transform=ax.transAxes, va='top',
            fontsize=9, bbox=dict(facecolor='white', edgecolor='black', boxstyle='square'))


def plot_projection_distributions(source, destination, run, *, phase=None):
    with source.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    title = f'{run} {phase} spark removal' if phase else run
    for axis in ('X', 'Y'):
        fits = [row for row in rows if row['axis'] == axis]
        for metric, column, quantity in (
            (f'{axis}_mean', 'mean_pixel', 'mean position'),
            (f'{axis}_RMS', 'rms_pixel', 'positional RMS'),
        ):
            values = [value for fit in fits if (value := num(fit[column])) is not None]
            if not values:
                continue
            fig, ax = plt.subplots(figsize=(7, 4.5))
            _, edges, _ = ax.hist(values, bins='auto', color=COLORS[0], edgecolor='white')
            ax.set_title(f'Distribution of {axis} {quantity} across background fits\n{title}')
            ax.set_xlabel(YLABEL[metric])
            ax.set_xlim(0, 256)
            ax.set_ylabel('Fit settings per bin')
            ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
            add_fit_distribution_stats(ax, values, edges)
            fig.tight_layout()
            fig.savefig(destination / f'{run}_{metric}_fit_distribution.png', dpi=150)
            plt.close(fig)
    plot_background_distribution(rows, destination / f'{run}_B_O_norm_fit_distribution.png', title)


def plot_background_distribution(rows, destination, title):
    by_axis = {'X': [], 'Y': []}
    for row in rows:
        value = num(row['background_norm_ms_per_s'])
        if value is not None:
            by_axis[row['axis']].append(value)
    values = by_axis['X'] + by_axis['Y']
    if not values:
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    _, edges, _ = ax.hist(list(by_axis.values()), bins=np.histogram_bin_edges(values, bins=20),
                         stacked=True, color=['blue', 'red'], edgecolor='white',
                         label=[f'{axis} ({len(group)})' for axis, group in by_axis.items()])
    ax.set_title(f'Distribution of normalized optical background across X and Y fits\n{title}')
    ax.set_xlabel(r'$B_O^{\mathrm{norm}}$ (ms/s)')
    ax.set_ylabel('Fit settings per bin')
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.62))
    add_fit_distribution_stats(ax, values, edges)
    fig.tight_layout()
    fig.savefig(destination, dpi=150)
    plt.close(fig)


def exported_spark_rows(src, dataset, kind, excluded):
    rows = []
    for path in sorted((src / 'optical_per_run').glob('*/run_summary.txt'),
                       key=lambda path: natural_key(path.parent.name)):
        summary = read_spark_summary(path)
        run = summary['runID']
        if run not in excluded:
            rows.append(dict(run=run, dataset=dataset, kind=kind or infer_kind(dataset, [run]),
                             v_over_p=num(summary.get('v_over_p_kVbar-1')),
                             **spark_values(summary),
                             **projection_values(summary)))
    return rows


def analyse_runs(src, out, rms_limit, warnings, issues):
    runs = sorted({p.name for sub in ('optical', 'charge') if (src / sub).is_dir()
                   for p in (src / sub).iterdir() if p.is_dir() and p.name != 'results'},
                  key=natural_key)
    rows = []
    for run in runs:
        opt, chg = src / 'optical' / run, src / 'charge' / run
        r = {'run': run}
        # Settings / run conditions
        settings = next((d / 'settings.csv' for d in (opt, chg) if (d / 'settings.csv').is_file()), None)
        if settings is None:
            issues.append(f'{run}: no settings.csv')
        else:
            try:
                r.update(read_settings(settings))
            except Exception as e:
                issues.append(f'{run}: settings: {e}')
        if r.get('settings_id') and r['settings_id'] != run:
            r['id_mismatch'] = f"settings ID '{r['settings_id']}'"
            warnings.append(f"{run}: settings ID is {r['settings_id']}; results kept under folder name {run}")

        # Optical: Blackbox integral.csv (ID, P, V0-V4, purity, mean, rms, %, x, y, time, cut, total)
        spark_report = opt / 'diagnostics' / 'spark_status.txt'
        spark_summary = opt / 'run_summary.txt'
        if spark_summary.is_file():
            try:
                summary = read_spark_summary(spark_summary)
                r.update(projection_values(summary))
                if any(key in r for key in POSITION_METRICS):
                    r['projection_position_unit'] = 'pixel'
                if spark_report.is_file() and spark_report.read_text().splitlines()[:1] in (
                    ['Mode: remove'], ['Mode: detect']
                ):
                    r.update(spark_values(summary))
            except (OSError, StopIteration, csv.Error) as error:
                issues.append(f'{run}: optical summary: {error}')
        oflags = []
        ic = opt / 'integral.csv'
        if ic.is_file():
            try:
                row = first_row(ic)
                r['optical'], r['optical_err'] = num(row[8]), num(row[9])
                r['exposure_time'] = num(row[15]) if len(row) > 15 else None
                if r['optical'] and r['optical_err'] is not None:
                    r['optical_rms_percent'] = 100 * r['optical_err'] / r['optical']
                    if r['optical_rms_percent'] > rms_limit:
                        oflags.append(f"large RMS {r['optical_rms_percent']:.1f}% > {rms_limit:g}%")
            except Exception as e:
                issues.append(f'{run}: optical integral.csv: {e}')
                oflags.append('unreadable integral.csv')
        elif opt.is_dir() and any(opt.iterdir()):
            # (An empty optical/<run>/ is only the folder `charge` creates for
            # charge_run.sh's run list; optical was not run, so nothing to report.)
            issues.append(f'{run}: no optical/{run}/integral.csv (optical analysis not run or failed)')
            oflags.append('no optical result')
        if opt.is_dir() and any(opt.iterdir()):
            dst = out / 'optical_per_run' / run
            dst.mkdir(parents=True, exist_ok=True)
            for name in ('run_summary.txt', 'run_summary_readable.txt'):
                if (opt / name).is_file():
                    shutil.copy2(opt / name, dst / name)
            variations = opt / 'diagnostics' / 'projection_variations.csv'
            if variations.is_file() and (opt / 'integral.csv').is_file():
                shutil.copy2(variations, dst / variations.name)
                plot_projection_distributions(variations, dst.parent, run)
            for rel, name in OPTICAL_PER_RUN.items():
                if (opt / rel).is_file():
                    shutil.copy2(opt / rel, dst / name)
                else:
                    issues.append(f'{run}: missing optical/{run}/{rel}')
            for name in ('tot-vs-time-before-sparks.png', 'tot-vs-time-spark-removal.png',
                         'tot-distribution-before-sparks.png'):
                diagnostic = opt / 'diagnostics' / name
                if diagnostic.is_file():
                    shutil.copy2(diagnostic, dst / name)
            for rel in OPTICAL_FAILURE_NOTES:
                if (opt / rel).is_file():
                    reason = (opt / rel).read_text().splitlines()[0]
                    issues.append(f'{run}: {reason} (see optical/{run}/{rel})')
        r['optical_flags'] = '; '.join(oflags)

        # Charge: V50 from pulseheights.csv
        ph = chg / 'pulseheights.csv'
        if ph.is_file():
            try:
                r.update(v50_analysis(ph, run, out / 'v50_distributions'))
            except Exception as e:
                issues.append(f'{run}: V50: {e}')
                r['v50_flags'] = f'V50 failed: {e}'
        elif chg.is_dir():
            issues.append(f'{run}: no charge/{run}/pulseheights.csv')
            r['v50_flags'] = 'no pulseheights.csv'

        # Ratio with uncorrelated spreads: sigma_R = R sqrt((sO/O)^2 + (sV/V)^2)
        o, so, v, sv = r.get('optical'), r.get('optical_err'), r.get('v50'), r.get('v50_err')
        if o is not None and v:
            r['ratio'] = o / v
            if so is not None and sv is not None and o:
                r['ratio_err'] = abs(r['ratio']) * np.hypot(so / o, sv / v)
        rows.append(r)
    return rows


# ---------------------------------------------------------------- plotting
def flagged(r, metric):
    if metric in OPTIONAL_METRICS:
        return False
    if metric == 'optical':
        return bool(r.get('optical_flags'))
    if metric == 'v50':
        return bool(r.get('v50_flags'))
    return bool(r.get('optical_flags') or r.get('v50_flags'))


def draw(ax, pts, color, kind):
    marker, filled = MARKER[kind]
    for x, y, e, flag in pts:
        ax.errorbar(x, y, yerr=e, fmt=marker, color=color, mfc=color if filled else 'none',
                    ms=6, mew=1.3, capsize=3, lw=1)
        if flag:
            ax.plot(x, y, marker='x', color='k', ms=5, mew=1.2, zorder=5)


def legend(ax, entries, any_flag):
    handles = [Line2D([], [], ls='none', marker=MARKER[k][0], color=c,
                      mfc=c if MARKER[k][1] else 'none', mew=1.3, label=n) for n, c, k in entries]
    if any_flag:
        handles.append(Line2D([], [], ls='none', marker='x', color='k', label='review flag (see notes)'))
    if handles:
        ax.legend(handles=handles, fontsize=8)


def finish(ax, scale, pts, *, signed=False):
    """Linear: y from 0 to 1.1 x largest central value. Returns clipped indices."""
    ax.set_yscale(scale)
    ax.grid(alpha=.2)
    if not pts:
        ax.text(.5, .5, 'No valid results available', transform=ax.transAxes, ha='center', va='center')
        return []
    if scale == 'log' or signed:
        return []
    top = 1.1 * max(p[1] for p in pts)
    if top <= 0:
        return []
    ax.set_ylim(0, top)
    clipped = [i for i, (_, y, e, _) in enumerate(pts) if e is not None and y + e > top]
    if clipped:
        ax.set_title((ax.get_title() + '\n' if ax.get_title() else '')
                     + 'some error bars extend beyond the y axis (see warnings.txt)', fontsize=9)
    return clipped


def points(rows, metric, xof, scale):
    out, keep = [], []
    for r in rows:
        x, y = xof(r), r.get(metric)
        if x is None or y is None or (scale == 'log' and y <= 0):
            continue
        out.append((x, y, r.get(metric + '_err'), flagged(r, metric)))
        keep.append(r)
    return out, keep


def summary_plots(rows, dataset, kind, folder, warnings, metrics=None):
    folder.mkdir(parents=True, exist_ok=True)
    names = [r['run'] for r in rows]
    index = {n: i for i, n in enumerate(names)}
    if metrics is None:
        metrics = ('optical', 'v50', 'ratio', *OPTIONAL_METRICS)
    for metric in metrics:
        if metric in OPTIONAL_METRICS and not any(r.get(metric) is not None for r in rows):
            continue
        for mode in ('streaming', 'physics'):
            for scale in (('linear',) if metric in ('ratio', *OPTIONAL_METRICS) else ('linear', 'log')):
                xof = (lambda r: index[r['run']]) if mode == 'streaming' else (lambda r: r.get('v_over_p'))
                pts, used = points(rows, metric, xof, scale)
                fig, ax = plt.subplots(figsize=(max(8, len(rows) * .48), 5.5) if mode == 'streaming' else (8, 5.5))
                draw(ax, pts, COLORS[0], kind)
                ax.set_title(dataset, fontsize=10)
                clipped = finish(ax, scale, pts, signed=metric in (*PROJECTION_METRICS, "S_O_over_B_O_ratio"))
                if clipped:
                    warnings.append(f'{metric} {mode} {scale}: upper error bar clipped for '
                                    + ', '.join(used[i]['run'] for i in clipped))
                if mode == 'streaming':
                    ax.set_xticks(range(len(names)), names, rotation=65, fontsize=8)
                    ax.set_xlabel('Run (acquisition order)')
                else:
                    ax.set_xlabel(VP_LABEL)
                ax.set_ylabel(YLABEL[metric])
                if metric in POSITION_METRICS:
                    ax.set_ylim(0, 256)
                elif metric == "S_O_over_B_O_ratio":
                    ax.set_ylim(bottom=0)
                legend(ax, [(dataset, COLORS[0], kind)] if pts else [], any(p[3] for p in pts))
                fig.tight_layout()
                fig.savefig(folder / f'{metric}_{mode}_{scale}.png', dpi=150)
                plt.close(fig)


def load_results(path, dataset=None):
    rows = []
    with path.open(newline='') as f:
        for row in csv.DictReader(f):
            r = {k: num(row.get(k)) for k in ('v_over_p', 'optical', 'optical_err', 'v50',
                                              'v50_err', 'ratio', 'ratio_err', *SPARK_METRICS)}
            r.update(projection_values(row))
            r['excluded'] = row.get('excluded', '').strip().lower() == 'yes'
            r['run'] = row.get('run', '')
            r['dataset'] = dataset or row.get('dataset', '')
            r['kind'] = row.get('kind') or infer_kind(r['dataset'], [r['run']])
            # history.csv has a single 'flag' column holding V50 review flags.
            r['v50_flags'] = row.get('v50_flags', row.get('flag', ''))
            r['optical_flags'] = row.get('optical_flags', '')
            rows.append(r)
    return rows


def add_figure_footnote(fig, footnote):
    if not footnote:
        return
    engine = fig.get_layout_engine()
    if isinstance(engine, matplotlib.layout_engine.ConstrainedLayoutEngine):
        engine.set(rect=(0, .09, 1, .91))
    else:
        fig.tight_layout(rect=(0, .09, 1, 1))
    fig.text(.08, .025, footnote, fontsize=8, ha='left', va='bottom', color='.25')


def comparison_plots(rows, folder, paper, warnings, notes, metrics=None, *, summary_dataset=None,
                     footnote=None):
    folder.mkdir(parents=True, exist_ok=True)
    datasets = sorted({r['dataset'] for r in rows}, key=natural_key)
    color = {d: COLORS[i % len(COLORS)] for i, d in enumerate(datasets)}
    kind = {r['dataset']: r['kind'] for r in rows}
    if metrics is None:
        metrics = ('optical', 'v50', 'ratio', *OPTIONAL_METRICS)
    for metric in metrics:
        if metric in OPTIONAL_METRICS and not any(r.get(metric) is not None for r in rows):
            continue
        scale = 'log' if metric in ('optical', 'v50') else 'linear'
        fig, ax = plt.subplots(figsize=(9, 6))
        allpts, used_all, entries = [], [], []
        for d in datasets:
            pts, used = points([r for r in rows if r['dataset'] == d], metric, lambda r: r.get('v_over_p'), scale)
            if pts:
                draw(ax, pts, color[d], kind[d])
                entries.append((d, color[d], kind[d]))
                allpts += pts
                used_all += used
        clipped = finish(ax, scale, allpts, signed=metric in (*PROJECTION_METRICS, "S_O_over_B_O_ratio"))
        if clipped:
            warnings.append(f'{metric} comparison: upper error bar clipped for '
                            + ', '.join(f"{used_all[i]['dataset']}/{used_all[i]['run']}" for i in clipped))
        ax.set_xlabel(VP_LABEL)
        ax.set_ylabel(YLABEL[metric])
        if metric in POSITION_METRICS:
            ax.set_ylim(0, 256)
        elif metric == "S_O_over_B_O_ratio":
            ax.set_ylim(bottom=0)
        legend(ax, entries, any(p[3] for p in allpts))
        fig.tight_layout()
        if metric in SPARK_METRICS and len(entries) == 1:
            ax.set_title('One dataset with spark measurements')
        filename = f'{metric}_overlay.png' if metric in OPTIONAL_METRICS else f'{metric}_physics_comparison.png'
        summary_name = f'{metric}_physics_{scale}.png'
        summary_plot = folder.parent / 'summary_plots' / summary_name
        if len(entries) == 1 and entries[0][0] == summary_dataset and summary_plot.is_file():
            shutil.copy2(summary_plot, folder / summary_name)
        else:
            add_figure_footnote(fig, footnote)
            fig.savefig(folder / filename, dpi=150)
        plt.close(fig)

    if paper is None:
        return
    from PIL import Image, ImageDraw, ImageFont
    image = Image.open(paper).convert('RGB')
    if image.size != PAPER_SIZE:
        raise ValueError(f'paper overlay must be the calibrated {PAPER_SIZE[0]}x{PAPER_SIZE[1]} Fig. 26 image')
    dr = ImageDraw.Draw(image)
    font_path = Path(matplotlib.get_data_path()) / 'fonts/ttf/DejaVuSans.ttf'   # ships with matplotlib
    font = ImageFont.truetype(str(font_path), 30) if font_path.exists() else ImageFont.load_default()
    (x0, x1, xa, xb), (y0, y1, ya, yb) = PAPER_X, PAPER_Y
    outside = []

    def glyph(x, y, k, c, s=16):
        shape, filled = MARKER[k]
        box = (x - s, y - s, x + s, y + s)
        if shape == 's':
            dr.rectangle(box, outline=c, fill=None if not filled else c, width=5)
        else:
            dr.ellipse(box, outline=c, fill=c if filled else None, width=5)

    for r in rows:
        vp, o = r.get('v_over_p'), r.get('optical')
        if vp is None or o is None:
            continue
        if not (xa <= vp <= xb and ya <= o <= yb):
            outside.append(r)
            notes.append((r['dataset'], r['run'], 'outside paper axes',
                          f'V/P={vp:.3g}, S_O={o:.3g} not drawn on paper overlay'))
            continue
        x = x0 + (x1 - x0) * (vp - xa) / (xb - xa)
        y = y0 - (np.log10(o) - np.log10(ya)) / (np.log10(yb) - np.log10(ya)) * (y0 - y1)
        glyph(x, y, r['kind'], color[r['dataset']])
        if flagged(r, 'optical'):
            dr.line((x - 10, y - 10, x + 10, y + 10), fill='black', width=4)
            dr.line((x - 10, y + 10, x + 10, y - 10), fill='black', width=4)
    # Legend in the empty lower-right part of the paper's axes.
    ly = 1600 - 40 * len(datasets)
    for d in datasets:
        glyph(1960, ly + 17, kind[d], color[d], s=12)
        dr.text((1990, ly), d, fill=color[d], font=font)
        ly += 40
    if footnote:
        canvas = Image.new('RGB', (image.width, image.height + 120), 'white')
        canvas.paste(image, (0, 0))
        ImageDraw.Draw(canvas).multiline_text((100, image.height + 20), footnote,
                                              fill='#404040', font=font)
        image = canvas
    image.save(folder / 'optical_paper_overlay.png')
    write_csv(folder / 'paper_overlay_out_of_range.csv', outside, ['dataset', 'run', 'v_over_p', 'optical'])


# ---------------------------------------------------------------- tables / notes
RESULT_FIELDS = ['dataset', 'kind', 'run', 'v_over_p', 'optical', 'optical_err', 'optical_rms_percent',
                 'optical_flags', 'v50', 'v50_err', 'v50_entries', 'v50_nonfinite', 'v50_outside_0_6000',
                 'v50_flags', 'ratio', 'ratio_err', *OPTIONAL_METRICS, *OPTICAL_RMS_FIELDS, 'projection_position_unit', 'excluded']
CONDITION_FIELDS = ['run', 'settings_id', 'id_mismatch', 'V0', 'V1', 'V2', 'V3', 'V4', 'pressure_mbar',
                    'methane_fraction', 'exposure_time', 'v_over_p', 'unavailable']


def run_conditions(rows, out):
    table = []
    for r in rows:
        t = {k: r.get(k) for k in CONDITION_FIELDS}
        t['unavailable'] = ', '.join(k for k in CONDITION_FIELDS[3:-1] if r.get(k) is None)
        table.append(t)
    write_csv(out / 'run_conditions.csv', table, CONDITION_FIELDS)

    def fmt(v, digits=4):
        if v is None or v == '':
            return 'n/a'
        return f'{v:.{digits}g}' if isinstance(v, float) else str(v)
    cols = ['Run', 'V0', 'V1', 'V2', 'V3', 'V4', 'P (mbar)', 'CH4 frac.', 'Exposure', 'V43+21/P (kV/bar)', 'Notes']
    lines = ['# Run conditions', '',
             'Voltages, pressure and methane fraction are read from settings.csv (columns ID, P, V0-V4, '
             'Blackbox "purity", reported here as methane fraction). Exposure is the Blackbox optical '
             '`total_time` (integral.csv), in the units that analysis uses. V43+21/P = (V4 - V3 + V2 - V1)/P '
             'in kV/bar (numerically V/mbar). n/a = unavailable. These conditions are as recorded, not '
             'independently verified.', '',
             '| ' + ' | '.join(cols) + ' |', '|' + '---|' * len(cols)]
    for t in table:
        notes = '; '.join(x for x in (t['id_mismatch'] and f"ID mismatch: {t['id_mismatch']}",
                                      t['unavailable'] and f"missing: {t['unavailable']}") if x)
        lines.append('| ' + ' | '.join([t['run']] + [fmt(t[k]) for k in ('V0', 'V1', 'V2', 'V3', 'V4',
                     'pressure_mbar', 'methane_fraction', 'exposure_time')] + [fmt(t['v_over_p'], 5), notes]) + ' |')
    (out / 'run_conditions.md').write_text('\n'.join(lines) + '\n')


README = """Plots and tables made by `plot` following PLOT_GUIDE.md.

Input:   {src}
Dataset: {dataset} ({kind} runs)

run_conditions.csv/.md  V0-V4, pressure, methane fraction, exposure, V43+21/P per run.
results.csv             Numerical results, spreads and review flags per run.
optical_per_run/        Four classic plots plus the available spark diagnostics.
                        The classic plots use the 4to8, 2nd-degree background setting.
v50_distributions/      Channel-B V50 histogram per run (own x range; peak estimate dashed).
summary_plots/          {{optical,v50}}_{{streaming,physics}}_{{linear,log}}.png and
                        ratio_{{streaming,physics}}_linear.png for this dataset.
{comparison_help}
warnings.txt, status.txt  Metadata/plot warnings and missing or failed inputs.

Markers: hollow squares = pressure runs, solid circles = voltage runs, diamonds = unknown
type; a black x marks a point with a review flag in results.csv.
Excluded from summary and comparison plots: {excluded} (values remain in results.csv).

Spreads
- Optical (S_O^norm): error bar = RMS reported by the Blackbox optical analysis. Flagged
  when RMS/S_O > {rms:g}%.
- V50: {v50}
  Error bar = that estimated width, a spread of the distribution, not a validated
  uncertainty on the peak position. A missing or failed estimate is not evidence of no events.
- Ratio R = S_O^norm/V50: sigma_R = R*sqrt((sigma_O/O)^2 + (sigma_V50/V50)^2), treating the
  two spreads as uncorrelated. Indicative spread, not a full uncertainty.
- Linear plots: y maximum = 1.1 x largest central value; clipped error bars are noted on the
  plot and in warnings.txt. Log plots use automatic limits.
Charge p1 is not used for any C or O/C plot (C = V50). Results are preliminary: review low
statistics, peak-finder fallback, high-end pile-up, missing results and large optical RMS.
"""


def main():
    ap = argparse.ArgumentParser(prog='plot', description='Make the PLOT_GUIDE.md plots from an optical/charge output folder.')
    ap.add_argument('-i', '--input', required=True, type=Path, help='output folder of `optical`/`charge` (or a dataset)')
    ap.add_argument('-o', '--output', required=True, type=Path, help='folder for plots and tables')
    ap.add_argument('--dataset', help='dataset name used in legends and comparisons (default: input folder name)')
    ap.add_argument('--kind', choices=['pressure', 'voltage'], help='run type for markers (default: from dataset/run names)')
    ap.add_argument('--exclude', default='prp2-04,prp3-04', help="runs left out of summary/comparison plots ('' for none)")
    ap.add_argument('--history', type=Path, default=REFERENCE / 'history.csv', help='baseline results to compare against')
    ap.add_argument('--compare', type=Path, nargs='*', default=[], help='earlier `plot` output folders to include in comparisons')
    ap.add_argument('--paper-overlay', type=Path, default=REFERENCE / 'figure26_reference.png', help='calibrated 2750x2000 Fig. 26 image')
    ap.add_argument('--no-paper', action='store_true', help='skip the paper overlay')
    ap.add_argument('--no-comparisons', action='store_true', help='generate dataset plots only')
    ap.add_argument('--rms-flag-percent', type=float, default=10.0, help='flag optical results with RMS above this %% of S_O (default 10)')
    ap.add_argument('--share-summary-plots', action='store_true',
                    help='reuse the physics plot for comparisons showing only the current dataset')
    ap.add_argument('--spark-only', action='store_true',
                    help='generate spark and projection observable plots from an exported plots folder containing optical_per_run/')
    a = ap.parse_args()

    src, out = a.input.expanduser().resolve(), a.output.expanduser().resolve()
    if a.spark_only:
        dataset = a.dataset or src.name
        excluded = {run.strip() for run in a.exclude.split(',') if run.strip()}
        rows = exported_spark_rows(src, dataset, a.kind, excluded)
        if not rows:
            ap.error(f'{src} has no exported run summaries')
        summary_plots(rows, dataset, rows[0]['kind'], out / 'summary_plots', [], metrics=OPTIONAL_METRICS)
        if not a.no_comparisons:
            comparison_rows = [r for directory in a.compare for r in load_results(directory / 'results.csv')
                               if r['dataset'] != dataset and r['run'] not in excluded]
            comparison_plots(rows + comparison_rows, out / 'comparisons', None, [], [], metrics=OPTIONAL_METRICS)
        return 0
    if not (src / 'optical').is_dir() and not (src / 'charge').is_dir():
        ap.error(f'{src} has neither optical/ nor charge/')
    if out == src:
        ap.error('output must differ from input')
    dataset = a.dataset or src.name
    excluded = {x.strip() for x in a.exclude.split(',') if x.strip()}

    out.mkdir(parents=True, exist_ok=True)
    subfolders = ('optical_per_run', 'v50_distributions', 'summary_plots')
    if not a.no_comparisons:
        subfolders += ('comparisons',)
    for sub in subfolders:
        shutil.rmtree(out / sub, ignore_errors=True)
    (out / 'v50_distributions').mkdir()

    warnings, issues = [], []
    rows = analyse_runs(src, out, a.rms_flag_percent, warnings, issues)
    if not rows:
        ap.error(f'no run folders found in {src}/optical or {src}/charge')
    kind = a.kind or infer_kind(dataset, [r['run'] for r in rows])
    if kind == 'unknown':
        warnings.append(f'could not tell whether {dataset} is a pressure or voltage dataset; '
                        'diamond markers used (set --kind)')
    for r in rows:
        r.update(dataset=dataset, kind=kind, excluded='yes' if r['run'] in excluded else '')

    run_conditions(rows, out)
    write_csv(out / 'results.csv', rows, RESULT_FIELDS)
    write_combined_run_summary(out)
    shown = [r for r in rows if r['run'] not in excluded]
    summary_plots(shown, dataset, kind, out / 'summary_plots', warnings)

    if not a.no_comparisons:
        # Comparison set: history baseline, earlier plot outputs, then this dataset.
        # A dataset's newest results replace its older ones.
        groups = {}
        if a.history and a.history.is_file():
            for r in load_results(a.history):
                groups.setdefault(r['dataset'], []).append(r)
        elif a.history:
            issues.append(f'history file not found: {a.history}')
        for d in a.compare:
            f = d.expanduser() / 'results.csv'
            if f.is_file():
                prev = load_results(f)
                for name in {r['dataset'] for r in prev}:
                    groups[name] = [r for r in prev if r['dataset'] == name]
            else:
                issues.append(f'--compare {d}: no results.csv')
        groups[dataset] = [dict(r) for r in rows]
        combined, notes = [], []
        for name, rs in groups.items():
            for r in rs:
                if r['run'] in excluded:
                    notes.append((name, r['run'], 'excluded', 'left out of summary and comparison plots'))
                    continue
                for key in ('optical_flags', 'v50_flags'):
                    if r.get(key):
                        notes.append((name, r['run'], 'provisional', f"{key.split('_')[0]}: {r[key]}"))
                if r.get('v_over_p') is None:
                    notes.append((name, r['run'], 'missing V/P', 'not on physics plots'))
                combined.append(r)
        paper = None if a.no_paper or not a.paper_overlay.is_file() else a.paper_overlay
        if paper is None and not a.no_paper:
            issues.append(f'paper overlay image not found: {a.paper_overlay}')
        comparison_plots(combined, out / 'comparisons', paper, warnings, notes,
                         summary_dataset=dataset if a.share_summary_plots else None)
        with (out / 'comparisons' / 'notes.csv').open('w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['dataset', 'run', 'category', 'detail'])
            w.writerows(sorted(notes, key=lambda n: (natural_key(n[0]), natural_key(n[1]))))

    (out / 'warnings.txt').write_text('\n'.join(warnings) + '\n' if warnings else 'No warnings.\n')
    (out / 'status.txt').write_text('\n'.join(issues) + '\n' if issues else 'No missing or failed inputs.\n')
    (out / 'README.txt').write_text(README.format(src=src, dataset=dataset, kind=kind,
                                    excluded=', '.join(sorted(excluded)) or 'none',
                                    rms=a.rms_flag_percent, v50=V50_METHOD,
                                    comparison_help=(
                                        'Use scripts/compare-optical-results.py to compare selected exports.'
                                        if a.no_comparisons else
                                        'comparisons/            Physics comparisons and optional Figure 26 overlay.'
                                    )))

    n_opt = sum(r.get('optical') is not None for r in rows)
    n_v50 = sum(r.get('v50') is not None for r in rows)
    print(f'{len(rows)} runs: {n_opt} optical results, {n_v50} V50 estimates ({dataset}, {kind})')
    print(f'Issues: {len(issues)} (status.txt); warnings: {len(warnings)} (warnings.txt)')
    print(f'Plots: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
