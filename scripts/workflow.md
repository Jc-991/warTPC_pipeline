# unzip.sh, workflow.sh and optical-analysis.sh

Two scripts take an uploaded dataset from `/storage/phsccs_grp/transfer/` to
plots:

1. **`unzip.sh`** unzips the ZIP into a data folder.
2. **`workflow.sh`** analyses the unzipped folder: optical and/or charge, then
   the plots listed in `PLOT_GUIDE.md`.

```bash
cd scripts
./unzip.sh example.zip ~/warTPC/data                      # -> ~/warTPC/data/example/
./workflow.sh ~/warTPC/data/example ~/warTPC/results      # -> ~/warTPC/results/example_results/
```

`example.zip` stands for whatever ZIP you uploaded.

To redo only some optical runs later, use
[`optical-analysis.sh`](#optical-analysissh-chosen-runs-only). Unzip once; after that,
run `workflow.sh` on the folder as often as you like.

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
./workflow.sh <dataset_dir> <output_dir> [--run optical|charge|both] [--kind pressure|voltage] [--no-plot]
```

| Argument / option | Meaning |
|---|---|
| `<dataset_dir>` | Unzipped dataset folder, containing `optical/` and/or `charge/`. Usually made by `unzip.sh`, but any dataset folder works. It is only read, never changed |
| `<output_dir>` | Results go to `<output_dir>/<name>_results/`, where `<name>` is the dataset folder's name. Created if missing |
| `--run optical\|charge\|both` | Which analysis to run. Default `both`. With `optical` or `charge`, a missing `optical/` or `charge/` folder counts as a failure; with `both`, a missing folder is just skipped |
| `--kind pressure\|voltage` | Whether this is a pressure or a voltage dataset, which sets the plot markers. Default: guessed from the dataset name (`pressure-pass-*`, `prp*`, `voltage-run-*`, `vr*`). If the guess fails, diamonds are used |
| `--no-plot` | Skip the plotting step |
| `-h, --help` | Show help |

`<name>` is also the dataset name in plot legends and comparisons, so a
descriptive name such as `pressure-pass-06` gives the clearest plots.

Giving a ZIP instead of a folder stops with
`example.zip is not an unzipped folder; unzip it first: ...unzip.sh example.zip <data_dir>`.

### Examples

```bash
# Optical and charge, then plots
./workflow.sh ~/warTPC/data/example ~/warTPC/results

# State that it is a voltage dataset
./workflow.sh ~/warTPC/data/example ~/warTPC/results --kind voltage

# Only optical, no plots
./workflow.sh ~/warTPC/data/example ~/warTPC/results --run optical --no-plot

# Only charge (e.g. after optical has already run into the same results)
./workflow.sh ~/warTPC/data/example ~/warTPC/results --run charge
```

### What it does

| Step | Action | Stops with |
|---|---|---|
| 1 | Checks the dataset folder | `<dir> does not exist`, `<dir> has no optical/ or charge/ folder`, `... is not an unzipped folder` |
| 2 | Checks that the needed commands are built | `.../build/optical not found` |
| 3 | Creates `<output_dir>/<name>_results/` and starts the log | — |
| 4 | Runs `optical`, then `charge` (or only the one chosen with `--run`) | Doesn't stop: failed runs are reported and the next step still runs |
| 5 | Runs `plot` into `<name>_results/plots/` (unless `--no-plot`) | Doesn't stop |

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
./optical-analysis.sh <dataset_dir> <output_dir> [--runs LIST] [--kind pressure|voltage] [--no-plot]
./optical-analysis.sh <dataset_dir> --list
```

| Option | Meaning |
|---|---|
| `--runs LIST` | Runs to analyse, separated by commas or spaces. `3` = run number 3 from `--list`; `2-5` = numbers 2 to 5; `vr22-07` = a run name; `'vr22-1*'` = a name pattern (quote it); `all` = every run. Without `--runs`, the runs are listed and you are asked |
| `--list` | Only list the runs with their numbers |
| `--kind pressure\|voltage` | Marker type in the plots |
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
- `summary_plots/`, `comparisons/`, `v50_distributions/` and
  `optical_per_run/`.
- `status.txt` and `warnings.txt`.

The `plot` section of the main [README](../README.md#plot) describes each file.

## 2D images and X/Y projections

The quickest place to look is `plots/optical_per_run/<run>/`, which has one
folder per run:

| File | What it shows | When it exists |
|---|---|---|
| `2D_ToT_before_fit.png` | Integrated ToT map before the 2D Gaussian fit (linear colour scale); `+` marks the peak (hottest pixel) | Every run |
| `2D_ToT_with_slices.png` | The same map with the **X slice through the peak** (the pixel row at the peak) above and the **Y slice** (the pixel column at the peak) on the right, on shared pixel axes. Dashed lines on the map show where the slices are taken | Every run |
| `xy_projections_sideband_regions_4to8.png` | X and Y projections as the sideband step uses them: signal region, sideband limits and the sideband points the background polynomial is fitted to, **before** that fit (setting `4to8`) | Runs where the 2D fit worked, even if the sideband step then fails |
| `sideband_regions.csv` | For every setting and axis: the regions, the number of sideband points, and problems such as a sideband running off the chip | Same |
| `sideband_failed.txt` | Which sideband setting crashed (polynomial degree, axis, `<s>to<b>`) and the error | Runs whose sideband step crashed |
| `xy_slices_before_fit.png` | The X and Y slices through the peak as histograms (one bin per pixel, linear y), before any fit or background subtraction | Every run |
| `2D_integrated_ToT.png` | Final ToT image with the fit contours and the signal/sideband lines | Runs where the 2D fit worked |
| `x_projection_before_subtraction.png`, `y_projection_before_subtraction.png` | Full projection with the sideband points and the fitted polynomial background, i.e. just before subtraction | Runs where the 2D fit worked |
| `x_projection_signal.png`, `y_projection_signal.png` | Projection after background subtraction | Runs where the 2D fit worked |
| `combined_integral_distribution.png` | Combined signal-integral distribution | Runs where the 2D fit worked |
| `ToT_summary.txt` | Hits, pixels hit, total ToT, and the hottest pixel's share | Every run |
| `fit_parameters.txt` or `fit_failed.txt` | 2D fit result with warning flags, or the reason it failed | Every run |

All plots use a linear scale. The slices are taken through the hottest pixel,
which is the only peak known before the 2D fit; if a hot pixel is the hottest,
the slices go through it rather than the light spot, which the plots make
obvious. The sideband-region plots instead show the full summed projections,
because that is what the sideband fit uses.

The fit-dependent plots use the `2nd_degree` background and the `4to8`
signal/sideband setting.

The originals, including all other settings, are in `optical/<run>/`:
- before the 2D fit: `diagnostics/ToT-image-raw.png`, `diagnostics/ToT-image-projections.png`
  (map with slices), `diagnostics/projections-raw.png` (slices); the numbers,
  including the full row/column sums, are in `projections-raw.csv`
- after the 2D fit but before the sideband fit: `diagnostics/sideband_regions/<s>to<b>.png`
  for all 10 settings, and `regions.csv`
  (numbers in `projections-raw.csv`, maps in `perChipTOT.npy`, `perChipHIT.npy`)
- after the fit: `signal-integral_x|y/<degree>/<signal>to<sideband>/`, with
  `ToT-image.png`, `<s>to<b>.png` (before subtraction) and `<s>to<b>_signal.png`
  (after)

To list them all:
```bash
find <output_dir>/<name>_results -name '*.png' -path '*optical_per_run*'
```

`optical-analysis.py` has two fits: the 2D Gaussian fit on the ToT map, then a
polynomial background fit to the sidebands of each projection. The "every run"
files are made before both; the sideband-region files are made after the 2D fit
but before any sideband fit. So the projections exist even when either fit
fails.

**If a run failed:**
- `fit_failed.txt`: the 2D fit failed. Look at the before-fit plots, e.g. for a
  single hot pixel holding most of the ToT, or no clear light spot.
- `sideband_failed.txt`: the 2D fit worked but the sideband step crashed. It
  names the setting; look at `sideband_regions.csv` and the region plot for
  that setting (in `optical/<run>/diagnostics/sideband_regions/`), e.g. a
  sideband running off the chip or too few sideband points.

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
4. `plots/comparisons/notes.csv`: excluded and provisional points.

## Running only optical or only charge

`--run optical` or `--run charge` runs just that analysis. The plots are made
from whatever is in the results folder, so:
- after `--run optical` alone, the V50 and ratio plots are empty (no charge
  results yet);
- running the other one later, into the same `<output_dir>`, adds its results,
  and the plots are remade with both. The step that isn't rerun keeps its
  earlier results.

## Re-running

- **Same dataset folder, same `<output_dir>`:** optical and charge overwrite
  their earlier results, and the plots are remade. Nothing is unzipped.
- **To keep earlier results,** use a different `<output_dir>`.
- **To compare with an earlier pass,** run `build/plot` yourself with
  `--compare <earlier results>/plots`.

## Environment variables

| Variable | Default | Used by | Use |
|---|---|---|---|
| `WARTPC_STORAGE` | `/storage/phsccs_grp` | `unzip.sh` | Group storage to check |
| `WARTPC_TRANSFER` | `$WARTPC_STORAGE/transfer` | `unzip.sh` | Folder holding uploaded ZIPs |
| `WARTPC_BUILD` | `<repo>/build` | `workflow.sh` | Where `optical`, `charge` and `plot` are |
| `WARTPC_BLACKBOX` | `<repo>/blackbox` | `workflow.sh` | Other Blackbox scripts and tools to use. The folder must contain `optical_run.sh` / `charge_run.sh` next to the tools, so the original `~/warTPC/Blackbox` does not work here |
| `BLACKBOX_SETUP` | bundled `setup_blackbox.sh` | `workflow.sh` | Environment script that loads the Python/ROOT modules |
| `WARTPC_PYTHON` | `python3` | `workflow.sh` | Python used by `plot` |

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
