# unzip.sh, workflow.sh, optical-analysis.sh and optical-rebin-x.sh

Three scripts take an uploaded dataset from `/storage/phsccs_grp/transfer/` to
plots. The first two run once per dataset, when it is imported:

1. **`unzip.sh`** unzips the ZIP into a data folder.
2. **`stages/decode.sh`** decodes the optical raw data (straight from the ZIP) once into
   `~/warTPC/decoded_data/<name>/` (see [Decoding on import](#decoding-on-import)).
3. **`workflow.sh`** analyses the decoded data: spark cut, fits, then the plots
   listed in `PLOT_GUIDE.md`. It is optical only; charge is run on its own
   (see [Charge](#charge)).

```bash
cd scripts
./unzip.sh example.zip ~/warTPC/data                                   # -> ~/warTPC/data/example/
bash stages/decode.sh -i ~/warTPC/data/example -o ~/warTPC/decoded_data  # -> ~/warTPC/decoded_data/example/
./workflow.sh -i ~/warTPC/decoded_data/example -o ~/warTPC/results     # -> ~/warTPC/results/example_results/
```

`example.zip` stands for whatever ZIP you uploaded. Unzip and decode once;
after that, run `workflow.sh` on the decoded folder as often as you like.

Both scripts can be run from anywhere, e.g. `scripts/workflow.sh ...` from the
repository folder. `workflow.sh` finds `build/` relative to its own location.

## Before the first run

1. Build the commands once, on the cluster:
   ```bash
   cd path/to/directory/warTPC_pipeline
   cmake -S . -B build
   cmake --build build
   ```
   This creates `build/optical`, `build/charge` and `build/plot`, which the
   workflow calls.
2. Make sure `blackbox/tpx3dump` is present. It is not in git, so copy it from
   the original Blackbox folder:
   ```bash
   cp ~/warTPC/Blackbox/tpx3dump blackbox/
   chmod +x blackbox/tpx3dump
   ```
3. Work inside a compute allocation, not on a login node. The analysis can take
   a long time.

## unzip.sh

```
./unzip.sh <file.zip> <data_dir> [--force]
```

| Argument / option | Meaning |
|---|---|
| `<file.zip>` | ZIP name in `/storage/phsccs_grp/transfer/` (`.zip` can be left off), or a path to a ZIP anywhere |
| `<data_dir>` | The dataset is unzipped to `<data_dir>/<name>/`, where `<name>` is the ZIP name without `.zip`. Use space with room for the data |
| `--force` | Unzip again even if `<data_dir>/<name>/` exists. The old folder is replaced only after the new unzip succeeded |
| `-h, --help` | Show help |

| Step | Action | Stops with |
|---|---|---|
| 1 | For a bare ZIP name: checks that `/storage/phsccs_grp` and `transfer/` can be read | `no access to the data` |
| 2 | Checks that the ZIP exists | `<name> does not exist` |
| 3 | If `<data_dir>/<name>/` already holds the data, says so and stops (unless `--force`) | — (exit 0) |
| 4 | Tests the ZIP and checks free space | `<name> is damaged or not a ZIP file`, `not enough space in ...` |
| 5 | Unzips into a temporary folder, then moves the dataset to `<data_dir>/<name>/` | `has no optical/ or charge/ folder`, `contains more than one dataset folder` |

Notes:
- The dataset can be the top level of the ZIP or a single folder inside it.
  Either way it ends up as `<data_dir>/<name>/`, named after the ZIP.
- The `__MACOSX/` folder that ZIPs made on a Mac contain is removed.
- A failed unzip leaves nothing behind.
- The last line printed is always the dataset folder, ready for `workflow.sh`.
- The script can't tell if a ZIP was re-uploaded with new contents. Use
  `--force` to unzip it again.

## workflow.sh

```
./workflow.sh -i <decoded_dataset_dir> -o <output_dir>
              [--runs LIST] [--kind pressure|voltage] [--sparks on|off] [--veto B,A|off]
              [--rebin-x off|N]
```

| Argument / option | Meaning |
|---|---|
| `-i <decoded_dataset_dir>` | Decoded dataset from `decode.sh`, e.g. `~/warTPC/decoded_data/voltage-run-22-11-26`. Giving the raw folder instead stops with `... holds raw .tpx3 data; decode it first` |
| `-o <output_dir>` | Results go to `<output_dir>/<name>_results/`, where `<name>` is the dataset folder's name. Created if missing |
| `--runs LIST` | Comma-separated runs (default all) |
| `--sparks on\|off`, `--veto B,A\|off` | Spark cut (default on) and the veto around each flagged window (default `1,20`) |
| `--kind pressure\|voltage` | Whether this is a pressure or a voltage dataset, which sets the plot markers. Default: guessed from the dataset name (`pressure-pass-*`, `prp*`, `voltage-run-*`, `vr*`). If the guess fails, diamonds are used |
| `--rebin-x off\|N` | X rebinning in the optical analysis: neighbouring X pixels merged in pairs for the 2D Gaussian fit **and** for the X projection before the sideband fits (see [rebinX(2)](#rebinx2-switch---rebin-x-onoff)). Default `off` = Matt's original analysis |
| `-h, --help` | Show help |

`<name>` is also the dataset name in plot legends and comparisons, so a
descriptive name such as `pressure-pass-06` gives the clearest plots.

### Examples

```bash
# Optical (spark cut with the 1 s / 20 s veto), then plots and before/after pairs
./workflow.sh -i ~/warTPC/decoded_data/example -o ~/warTPC/results

# Two runs only, 5 ms windows without the veto
./workflow.sh -i ~/warTPC/decoded_data/example -o ~/warTPC/results --runs vr22-06,vr22-07 --veto off
```

### What it does

| Step | Action | Stops with |
|---|---|---|
| 1 | Checks the decoded folder | `<dir> does not exist`, `... holds raw .tpx3 data; decode it first` |
| 2 | Checks that the plot command is built | `.../build/plot not found` |
| 3 | Creates `<output_dir>/<name>_results/` and starts the log | — |
| 4 | Runs the fit stages below in order | Doesn't stop: failed runs are reported and the next step still runs |
| 5 | Plots and before/after pairs into `<name>_results/plots/` | Doesn't stop |

## Decoding on import

```bash
bash scripts/stages/decode.sh -i <dataset.zip | raw_dataset_dir> -o ~/warTPC/decoded_data [--runs LIST] [--force] [--timeout MIN] [--tmp DIR]
```

Run this once per dataset, when it is imported. `-i` can be the uploaded ZIP
itself: a bare name such as `voltage-run-18-11-26.zip` is found in
`/storage/phsccs_grp/transfer/`. The ZIP is unzipped into a temporary folder
(inside the output folder, or `--tmp DIR`), decoded, and the temporary copy is
deleted, so no unzipped raw copy is kept. A ZIP whose runs are all decoded
already is skipped without unzipping. All uploaded voltage runs at once:

```bash
for z in /storage/phsccs_grp/transfer/voltage-run-*.zip; do
  bash scripts/stages/decode.sh -i "$z" -o ~/warTPC/decoded_data
done
```

It runs `tpx3dump` on every `optical/<run>/rawdata_000000.tpx3` and keeps
only what the analysis reads:

```
~/warTPC/decoded_data/<name>/
├── optical/<run>/
│   ├── output.hdf5      tpx3dump output (the hits)
│   └── settings.csv     ID, pressure, voltages, methane fraction
├── logs/decode/<run>.log
└── decode_status.txt    last pass: decoded, skipped, failed (with the reason)
~/warTPC/decoded_data/decode_report.tsv   every run attempted, all datasets (appended)
```

`decode_report.tsv` has one line per run each time it is decoded: time,
dataset, run, `OK` / `TIMEOUT` / `FAILED`, seconds and the reason. To list the
runs that went over the time limit: `grep TIMEOUT ~/warTPC/decoded_data/decode_report.tsv`.

- Runs already decoded are skipped; `--force` redoes them. `settings.csv` is
  refreshed if the raw dataset's copy has changed.
- A run taking longer than `--timeout MIN` (default 10, `0` = no limit) is
  stopped and marked failed, and the next run starts. A failed run never stops
  the others; redo it with `--runs <run>` (and a longer `--timeout` if needed).
- Charge has no decode step (it reads `waveforms.csv` from the raw dataset), so
  nothing for charge is stored here.
- Results folders link to the stored HDF5 rather than copying it
  (`<name>_results/decoded` points at `decoded_data/<name>/optical`), so
  **keep the decoded folder** while you still use those results.

## Optical stages: running one step at a time

After decoding, the optical part of `workflow.sh` is three scripts in
`scripts/stages/`. Each works on a results folder `R`
(`<output_dir>/<name>_results`), can be rerun on its own, takes `--runs LIST`
(names or quoted patterns such as `'vr22-1*'`), and prints `-h` help. When
something breaks, rerun only the failing stage.

| Stage | Command | Reads | Writes |
|---|---|---|---|
| fit, uncut | `stages/fit.sh -r R -d <decoded_dataset_dir> --spark off` | `decoded_data/<name>/optical/` (remembered as `R/decoded`, so `-d` can be left out later) | `R/before/optical/<run>/`, `R/before/optical_status.txt`; log `R/before/logs/fit/<run>.log` |
| fit, cut | `stages/fit.sh -r R --spark remove [--veto 1,20]` | `R/decoded/` | `R/optical/<run>/`, `R/optical_status.txt`, `R/spark_counts.csv`; log `R/logs/fit/<run>.log` |
| plot | `stages/plot.sh -r R --from before`, then `stages/plot.sh -r R` | the fit folder | `R/before/plots/`, `R/plots/` (replaced each time) |
| pair | `stages/pair.sh -r R` | `R/before/plots/`, `R/plots/` | `R/paired/` (kept), then `R/plots/optical_per_run/` and the plot IDs |

Notes:
- `fit.sh` runs `blackbox/optical-analysis.py` directly on the decoded HDF5, so
  a refit never repeats `tpx3dump`. Each selected run's folder is replaced and
  the other runs are kept, so a folder can mix settings if you refit only some
  runs; `spark_status.txt` in each run's `diagnostics/` records what was used.
- `--analysis FILE` swaps in another analysis script; `--rebin-x N` as in `workflow.sh`.
- Without pairing (`--sparks off` or no before fit), use
  `stages/plot.sh -r R --organise` to give the plots their IDs.
- On Hammer each stage loads `blackbox/setup_blackbox.sh` itself.

`workflow.sh` applies the veto by default (`--veto 1,20`: every hit from 1 s
before to 20 s after each flagged 5 ms window is removed, and that time is
taken off the exposure). `--veto off` keeps only the 5 ms windows; `--veto B,A`
sets other margins. `fit.sh` itself has no default: pass `--veto` explicitly.

The ToT-versus-arrival-time images use 5 ms time columns, the same windows as
the spark grouping. A full run has more columns than the image has pixels, so
each pixel shows the largest 5 ms bin it covers (the colour bar says how many).

Example, redoing the cut fit and plots for one run with a veto:

```bash
bash scripts/stages/fit.sh  -r "$R" --spark remove --veto 1,20 --runs vr22-07
bash scripts/stages/plot.sh -r "$R"
bash scripts/stages/pair.sh -r "$R"
```

## optical-analysis.sh: chosen runs only

`optical-analysis.sh` runs only the optical analysis, on the runs you choose,
into the same results folder as `workflow.sh`. Use it to redo a few runs (e.g.
ones that failed) without rerunning the whole dataset.

```bash
./optical-analysis.sh ~/warTPC/data/example --list                         # show the runs, numbered
./optical-analysis.sh ~/warTPC/data/example ~/warTPC/results --runs 2,5-7  # analyse runs 2, 5, 6, 7
./optical-analysis.sh ~/warTPC/data/example ~/warTPC/results               # asks which runs
```

```
./optical-analysis.sh <dataset_dir> <output_dir> [--runs LIST] [--kind pressure|voltage]
                      [--rebin-x on|off] [--no-plot]
./optical-analysis.sh <dataset_dir> --list
```

| Option | Meaning |
|---|---|
| `--runs LIST` | Runs to analyse, separated by commas or spaces. `3` = run number 3 from `--list`; `2-5` = numbers 2 to 5; `vr22-07` = a run name; `'vr22-1*'` = a name pattern (quote it); `all` = every run. Without `--runs`, the runs are listed and you are asked |
| `--list` | Only list the runs with their numbers |
| `--kind pressure\|voltage` | Marker type in the plots |
| `--analysis FILE` | Use FILE instead of `blackbox/optical-analysis.py`, e.g. `../blackbox/optical-analysis-rebin-x.py` |
| `--rebin-x off\|N` | X rebinning in the optical analysis: neighbouring X pixels merged in pairs for the 2D Gaussian fit **and** for the X projection before the sideband fits (see [rebinX(2)](#rebinx2-switch---rebin-x-onoff)). Default `off` = Matt's original analysis |
| `--rebin N` | Test: merge N×N pixels (N = 2, 4, 8, 16) before the 2D Gaussian fit. The rebinned map and slices are printed too, and the fit result is converted back to pixel units, so the rest of the analysis is unchanged. Default 1 = no rebinning |
| `--no-plot` | Skip the plots |

What it does:
1. Analyses only the chosen runs (in a temporary staging folder, so the
   Blackbox script never sees the other runs).
2. Replaces those runs' results in `<output_dir>/<name>_results/optical/<run>/`
   and their logs in `logs/optical/<run>.log`. **Other runs' results are
   kept.**
3. Rebuilds `optical/results/signals.csv` and `optical_status.txt` from all
   runs in the results folder, so they always cover every run.
4. Remakes the plots from everything in the results folder, including charge
   results if present.

Its own log is `logs/optical-analysis_<timestamp>.log`.

In a batch job there's no terminal to ask, so `--runs` is required there.

## Output

```
<data_dir>/
└── <name>/                      unzipped dataset (from unzip.sh; never changed)

<output_dir>/
└── <name>_results/
    ├── decoded -> ~/warTPC/decoded_data/<name>/optical   decoded runs (from decode.sh), shared
    ├── before/                  uncut fits (optical/<run>/) and their plots/
    ├── paired/                  before/after pairs as built by pair.sh (stage 4)
    ├── optical/<run>/           Blackbox optical output per run (output.hdf5, integral.csv, plots,
    │                            diagnostics/ with the 2D map and projections from before the fit)
    ├── optical/results/         signals.csv for all runs
    ├── charge/<run>/            Blackbox charge output per run (waveforms.root, signal.csv, plots)
    ├── charge/results/          signals.csv for all runs
    ├── logs/
    │   ├── workflow_<timestamp>.log   everything this script printed (optical, charge, plot)
    │   ├── optical_<timestamp>.log    whole optical step
    │   ├── charge_<timestamp>.log     whole charge step
    │   ├── optical/<run>.log          one data run, ending in "# result: OK" or "FAILED"
    │   └── charge/<run>.log
    ├── optical_status.txt       runs that failed in optical
    ├── charge_status.txt        runs that failed in charge
    └── plots/                   PLOT_GUIDE plots and tables (see below)
```

The large raw files in `<name>_results/optical/<run>/` are links back to the
dataset folder. **Keep the dataset folder** as long as you may rerun the
analysis.

`plots/` contains:
- `run_conditions.md`: voltages, pressure, methane fraction, exposure and V/P
  for each run.
- `results.csv`: the numbers behind every plot.
- `run_summary.txt`: tab-separated optical run summaries, one row per available run.
- `summary_plots/`, `v50_distributions/` and
  `optical_per_run/`.
- `status.txt` and `warnings.txt`.

The `plot` section of the main [README](../README.md#plot) describes each file.

## 2D images and X/Y projections

`plots/optical_per_run/<run>/` has four classic plots per run, drawn from the
4to8 setting (signal to 4σ, sideband to 8σ) with the 2nd-degree background
fit. It is the same four whether `--rebin-x` is on or off (with `on`, the X
plot has 128 bins):

| File | What it shows | Copied from `optical/<run>/` |
|---|---|---|
| `2D_integrated_ToT.png` | Integrated ToT image with the 2D Gaussian fit contours and the X signal/sideband edges | `signal-integral_x/2nd_degree/4to8/ToT-image.png` |
| `x_projection_signal.png` | X projection after background subtraction | `signal-integral_x/2nd_degree/4to8/4to8_signal.png` |
| `y_projection_signal.png` | Y projection after background subtraction | `signal-integral_y/2nd_degree/4to8/4to8_signal.png` |
| `combined_integral_distribution.png` | Stacked X and Y signal integrals of all 60 settings; its mean is the run's S_O | `Total-Stacked-signal-integral.png` |

A run that failed has none of these; `plots/status.txt` says why (see below).

In spark-removal mode, the per-run summary also includes these marked-up plots:

| File | What it shows |
|---|---|
| `tot-distribution-before-sparks.png` | Filled, stacked histogram of kept and removed hits, with two lines marking the all-hit mean ± 5 RMS |
| `tot-vs-time-spark-removal.png` | The original ToT-versus-arrival-time spectrum with individual removed hits circled |

The unannotated `tot-vs-time-before-sparks.png` remains available for comparison.
Other diagnostics stay in `optical/<run>/`:
- `diagnostics/`, made before the 2D fit: the map with slices
  (`ToT-image-projections.png`), `summary.txt`, the numbers in
  `projections-raw.csv` (slices and full row/column sums) and the raw maps
  `perChipTOT.npy`, `perChipHIT.npy`
- `diagnostics/sideband_regions/`, made after the 2D fit but before the
  sideband fit: the projections with signal/sideband regions for all 10
  settings, and `regions.csv`
- `signal-integral_x|y/<degree>/<signal>to<sideband>/`, made by the sideband
  step: `ToT-image.png`, `<s>to<b>.png` (before subtraction) and
  `<s>to<b>_signal.png` (after)

**If a run failed,** `plots/status.txt` gives the reason, and the matching note
is in `optical/<run>/diagnostics/`:
- `no_hits.txt`: the HDF5 file has no pixel hits.
- `fit_failed.txt`: the 2D fit failed. Look at `diagnostics/ToT-image-raw.png`
  and `diagnostics/projections-raw.png`, e.g. for a single hot pixel holding
  most of the ToT, or no clear light spot.
- `sideband_failed.txt`: the 2D fit worked but the sideband step crashed. It
  names the setting; look at `sideband_regions/regions.csv` and the region plot
  for that setting, e.g. a sideband running off the chip or too few sideband
  points.

To view them on a Mac, run this in a Mac terminal:
```bash
scp -r hammer:<path to>/<name>_results/plots/optical_per_run ~/Desktop/
```

## Logs

| Log | Contents | On re-run |
|---|---|---|
| `logs/workflow_<timestamp>.log` | Everything `workflow.sh` printed, the same as the terminal | New file each time |
| `logs/optical_<timestamp>.log`, `logs/charge_<timestamp>.log` | The whole optical / charge step, with a summary of failed runs at the end | New file each time |
| `logs/optical/<run>.log`, `logs/charge/<run>.log` | One data run's output, ending in `# result: OK` or `# result: FAILED` | Rewritten |

Errors from the dataset-folder and build checks appear only in the terminal,
because they stop the script before the results folder is created.
`unzip.sh` prints to the terminal only.

If you leave a long run going, you can follow it from another terminal:
```bash
tail -f <output_dir>/<name>_results/logs/workflow_*.log
```

## Exit status and checking the results

For both scripts:
- `0`: everything succeeded (for `unzip.sh`, also "already unzipped").
- `1`: something failed or is missing. `workflow.sh`'s last line then says
  `Workflow finished with failures`.
- `2`: wrong usage, for example a missing argument.

After a `workflow.sh` run, check these files in this order:
1. `optical_status.txt` and `charge_status.txt`: which runs failed. Each
   failed run's own log, `logs/optical/<run>.log` or `logs/charge/<run>.log`,
   shows why.
2. `plots/status.txt`: missing inputs, for example no `pulseheights.csv`.
3. `plots/warnings.txt`: settings-ID mismatches and clipped error bars.

## rebinX(2) switch: --rebin-x on|off

`workflow.sh` takes `--rebin-x 2` and `optical-analysis.sh` takes `--rebin-x on` for pairwise X rebinning. The default is `off` for both.
It sets `WARTPC_REBIN_X=1` for `blackbox/optical-analysis.py`, which then
merges neighbouring X pixels in pairs (columns 0+1, 2+3, ...) in two places:
1. the 2D Gaussian fit uses the 256 (Y) × 128 (X) ToT map. The fit runs in
   pixel coordinates (bin centre x = 2k + 0.5), and amplitude and offset are
   converted back to per-pixel values;
2. the X projection is merged into 128 bins **before** the sideband
   background fits, so the polynomials are fitted to, and the signal is
   integrated over, 128 X bins. The X plots in `signal-integral_x/` say
   "RebinX(2): 128 bins". The Y projection keeps 256 bins.

With `off`, the analysis is exactly Matt's original (checked on vr22-07: all
60 integrals identical). On vr22-07, `on` moves the X integrals by about
0.02–0.07 and the run's S_O from 0.052 to 0.075.

```bash
./workflow.sh <dataset_dir> <output_dir> --run optical --rebin-x 2
./optical-analysis.sh <dataset_dir> <output_dir> --runs vr22-07 --rebin-x on
```

Use a different `<output_dir>` for `on` and `off`, so the two can be compared.
The run's log header (`# rebin-x: on`) and `diagnostics/fit_parameters.txt`
(last line) record which was used. `--rebin-x on` cannot be combined with
`--rebin N`.

### optical-rebin-x.sh

`optical-analysis.sh ... --rebin-x on`, followed by two comparisons:

```bash
./optical-rebin-x.sh <dataset_dir> <output_dir> --runs vr22-07 --kind voltage
```

Options are those of `optical-analysis.sh` (`--runs`, `--list`, `--kind`,
`--no-plot`). After the analysis it:
1. saves the fit inputs, original vs X-rebinned map and projections, for every
   run: `rebin_x_inputs/<run>-before-fit.png`;
2. fits each run both ways and lists the centres, widths and which
   signal/sideband regions change: `rebin_x_fit_check/<run>.txt`.

`blackbox/optical-analysis-rebin-x.py` is the same rebinX(2) analysis as a
standalone copy of Matt's script (without this project's diagnostics); the
switch above does not need it.

`optical-analysis.sh --analysis FILE` runs any other version of the optical
analysis the same way.

## Rebinning test

To test fitting the 2D Gaussian on a coarser map, rebin before the fit:

```bash
./optical-analysis.sh <dataset_dir> <output_dir_1> --runs vr22-07              # as now
./optical-analysis.sh <dataset_dir> <output_dir_2> --runs vr22-07 --rebin 2    # 2x2 rebinned
```

Use two different output folders to compare. In each run's
`optical/<run>/diagnostics/fit_parameters.txt` the last line says which
rebinning was used; the parameters are always in original pixel units, so the
two can be compared directly. The 2D fit's starting point is the hottest
rebinned bin. Use `optical-analysis.sh --rebin 2` for this two-axis fit test.

## Charge

`workflow.sh` is optical only (`--run optical` is still accepted, for older
commands). Charge has no decode step and reads `charge/<run>/waveforms.csv`
from the raw dataset, so run it on its own into the same results folder, then
remake the plots so the V50 and ratio plots include it:

```bash
build/charge -i ~/warTPC/data/<name> -o ~/warTPC/results/<name>_results
bash scripts/stages/plot.sh -r ~/warTPC/results/<name>_results
bash scripts/stages/pair.sh -r ~/warTPC/results/<name>_results
```

Without charge results, the V50 and ratio plots are empty.

## Selecting runs with workflow.sh

Pass exact run folder names as a comma-separated list:

```bash
bash scripts/workflow.sh -i "$decoded" -o "$results" --runs vr22-06,vr22-07
```

If the standard results directory already exists,
the selected run gets a fresh directory with a suffix, printed by the workflow.

## Spark detection

`workflow.sh` enables grouped optical spark removal by default. It sums ToT
in occupied 5 ms detector-time windows. It flags windows above the grouped
mean plus 10 RMS,
removes all hits in those windows, and subtracts their overlap with the run
from the exposure. As in Matt’s original analysis, exposure is the last stored
ToA minus the first, divided by 1e13 to give seconds. The first stored hit is
time zero for the spark plots and grouping. The summary counts flagged windows
as sparks. The workflow fits the same
dataset before and after the cut, then writes ten PNGs,
`run_summary.txt`, and `run_summary_readable.txt` for each optical run under
`<name>_results/plots/optical_per_run/`. Copy that folder to transfer just
the plots and summaries. Use `--sparks off` for a single uncut fit.
For fits without plots, run `stages/fit.sh` on its own.

X rebinning is off by default. Use `--rebin-x 2` to merge pairs, or specify
`4`, `8` or `16` for the number of adjacent X pixels per bin. Both spark
passes use the same setting.


To run the paired vr22 spark study on Hammer, use the one-command runner from
the checkout in a compute session:

```bash
bash scripts/run-vr22-spark-study.sh
```

It defaults to `vr22-06` and `vr22-07`. Pass run IDs as separate arguments
to choose other runs from `vr22-06` through `vr22-13`. It runs the before
and after fits with the same X binning, creates the next free `vr22-spark-study-01`, `-02`, ... directory,
and prints the location of the `optical_per_run/<run>/` folders. Each folder
contains both summary files and ten PNGs: the after-cut 2D ToT image, the
ToT histogram, the arrival-time spectrum before the cut and with the
removed windows marked, and before/after pairs of
the X projection, Y projection, and combined integral distribution. The
runner removes its temporary files after successful packaging. Copy the
printed results directory with `scp -r` to transfer both run folders.

Set `WARTPC_SPARK_MODE=detect` before the optical command to report the ToT cut
and count hits above it while keeping every hit. For a single-run check:

```bash
WARTPC_SPARK_MODE=detect bash scripts/optical-analysis.sh "$dataset" "$results" --runs vr22-08
```

After reviewing the threshold, use `WARTPC_SPARK_MODE=remove` with a separate
results directory. The default is `off`. Each run writes
`optical/<run>/diagnostics/spark_status.txt` with the mode, ToT threshold,
whether removal was applied, the hit counts, and the usable exposure.
Both `detect` and `remove` also save
`optical/<run>/diagnostics/tot-vs-time-before-sparks.png` from all hits,
before tagging or masking any interval.

`Spark count` counts individual hits strictly above the all-hit mean ToT
plus 10 RMS. In removal mode this count matches the number of removed hits
marked on the plots. To count from saved HDF5 files without rerunning an optical fit,
run `python3 blackbox/spark_detection.py <run>/output.hdf5`.
The workflow and selected-run scripts write `spark_counts.csv` at the
dataset results root. The table includes every optical run in that folder
and leaves the count blank if no count was recorded. It is also produced
when spark removal is off or summary plotting is skipped.
Each completed optical run writes a tab-separated `run_summary.txt` with a
header and one data row for merging runs. `run_summary_readable.txt` displays
the same fields one per line. Both use seconds for exposure and include the
original and usable exposures, spark count, iteration count, and optical
signals before and after exposure normalization. It also includes the run
conditions, the fraction of original exposure removed, and the optical RMS
divided by the magnitude of the normalized signal. Both ratios are absolute
decimal fractions. A fraction with a zero or unavailable denominator is blank in the table and
shown as `N/A` in the readable file. With plotting enabled,
each run's summaries are also copied into its own `plots/optical_per_run/<run>/` folder.

The per-run canvases show entries, mean, RMS, underflow, and overflow. The
2D map describes ToT per pixel, the projections describe the plotted signal
residuals, and the ToT diagnostics describe the original hits.

The cut removes only hits whose ToT is strictly greater than the all-hit mean
plus 10 RMS. It masks hits before building the optical maps. Exposure is
unchanged because no time windows are excluded, and the HDF5 input stays
intact. To generate the marked-up plots from a saved HDF5 without rerunning
the optical fit, use
`python3 blackbox/spark_detection.py --removal-plots <plot_dir> <run>/output.hdf5`.

## Spark observables

The plotting stage writes streaming and physics plots for the number of
flagged windows and the absolute fraction of exposure removed (1 = 100%).
Streaming plots use run order. Physics plots use V/P. The comparison overlays
use V/P and include each dataset that has spark measurements. Historical data
without spark measurements does not contribute a series.

## Re-running

With plotting enabled, `plots/optical_per_run/<run>/` contains the four
standard optical PNGs, including when spark removal is on. To save the
additional per-axis plots, prefix the optical command with
`WARTPC_SIGNAL_PLOTS=1`.

- **Same dataset folder, same `<output_dir>`:** optical and charge overwrite
  their earlier results, and the plots are remade. Nothing is unzipped.
- **To keep earlier results,** use a different `<output_dir>`.
- **To compare selected exports,** run `scripts/compare-optical-results.sh`
  separately. Repeat `-i PATH` for each dataset, or use `--series LABEL PATH`
  for custom legend labels. PATH can point to
  an exported `plots/` folder or its `results.csv`. Write the comparisons to
  a new or empty directory with `--output`. Streaming, physics panels and
  overlays are enabled by default. Use `--no-spo` for overlays only or
  `--no-paper` to omit Figure 26. `--historical-charge` fills missing V50
  and optical/V50 from matching historical runs and records their provenance.
  Use `--compact-labels` for footnotes on recovered fits and
  `--exclude-runs RUN1,RUN2` to omit specific runs from the plots.

## Environment variables

| Variable | Default | Used by | Use |
|---|---|---|---|
| `WARTPC_STORAGE` | `/storage/phsccs_grp` | `unzip.sh` | Group storage to check |
| `WARTPC_TRANSFER` | `$WARTPC_STORAGE/transfer` | `unzip.sh` | Folder holding uploaded ZIPs |
| `WARTPC_BUILD` | `<repo>/build` | `workflow.sh` | Where `optical`, `charge` and `plot` are |
| `WARTPC_BLACKBOX` | `<repo>/blackbox` | `workflow.sh` | Other Blackbox scripts and tools to use. The folder must contain `optical_run.sh` / `charge_run.sh` next to the tools, so the original `~/warTPC/Blackbox` does not work here |
| `BLACKBOX_SETUP` | bundled `setup_blackbox.sh` | `workflow.sh` | Environment script that loads the Python/ROOT modules |
| `WARTPC_PYTHON` | `python3` | `workflow.sh` | Python used by `plot` |
| `WARTPC_REBIN_X` | `0` | `optical-analysis.py` | `1` = rebinX(2); set by `--rebin-x on` |

## Common problems

| Message | Script | What to do |
|---|---|---|
| `no access to the data` | unzip | You're not in the group that owns `/storage/phsccs_grp`, or the storage isn't mounted on this node. Check with `ls /storage/phsccs_grp/transfer` and `groups` |
| `<name> does not exist` | unzip | Check the spelling with `ls /storage/phsccs_grp/transfer`, and check that the upload has finished |
| `not enough space in ...` | unzip | Choose a `<data_dir>` on scratch or project space |
| `has no optical/ or charge/ folder` | both | The ZIP or folder has a different layout. It needs `optical/<run>/` and/or `charge/<run>/` |
| `contains more than one dataset folder` | unzip | Upload each dataset as its own ZIP |
| `... is not an unzipped folder; unzip it first` | workflow | You gave `workflow.sh` a ZIP. Run `unzip.sh` first and give `workflow.sh` the folder it prints |
| `run number 9 is not in 1-6`, `no run matches '...'` | optical-analysis | Check the run numbers and names with `--list` |
| `no --runs given (and no terminal to ask)` | optical-analysis | In a batch job, give `--runs` |
| `.../build/optical not found` | workflow | Build the project (see [Before the first run](#before-the-first-run)) |
| `charge requested, but <name> has no charge/ folder` (or `optical`) | workflow | The dataset has no data for the analysis chosen with `--run`. Check its contents, or use `--run both` |
