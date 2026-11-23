# workflow.sh

`workflow.sh` runs the whole analysis for one dataset ZIP uploaded to
`/storage/phsccs_grp/transfer/`. It unzips the file, runs the optical and charge
analyses, and makes the plots listed in `PLOT_GUIDE.md`.

```bash
cd scripts
./workflow.sh example.zip output/path/to/directory
```

`example.zip` stands for whatever ZIP you uploaded.

## Before the first run

1. Build the commands once, on the cluster:
   ```bash
   cd path/to/directory/warTPC_pipeline
   cmake -S . -B build
   cmake --build build
   ```
   This creates `build/optical`, `build/charge` and `build/plot`, which the
   workflow calls.
2. Make sure `blackbox/tpx3dump` is present. It is not in git, so either copy
   it from the Blackbox folder or set `WARTPC_BLACKBOX` (see
   [Environment variables](#environment-variables)).
3. Work inside a compute allocation, not on a login node. The analysis can take
   a long time.

## Usage

```
./workflow.sh <file.zip> <output_dir> [--run optical|charge|both] [--kind pressure|voltage] [--no-plot]
```

| Argument / option | Meaning |
|---|---|
| `<file.zip>` | ZIP name in `/storage/phsccs_grp/transfer/`. The `.zip` can be left off. A full path to a ZIP elsewhere also works, and so does an already unzipped dataset folder (see [Data that is already unzipped](#data-that-is-already-unzipped)) |
| `<output_dir>` | Where everything goes. Created if missing. The data is unzipped into `<output_dir>/<name>/` and results are written to `<output_dir>/<name>_results/`. Use scratch or project space with room for the data |
| `--run optical\|charge\|both` | Which analysis to run. Default `both`. With `optical` or `charge`, a missing `optical/` or `charge/` folder in the ZIP counts as a failure; with `both`, a missing folder is just skipped |
| `--kind pressure\|voltage` | Whether this is a pressure or a voltage dataset, which sets the plot markers. Default: guessed from the ZIP name (`pressure-pass-*`, `prp*`, `voltage-run-*`, `vr*`). If the guess fails, diamonds are used |
| `--no-plot` | Skip the plotting step |
| `-h, --help` | Show help |

`<name>` is the ZIP name without `.zip`. It's also the dataset name in plot
legends and comparisons, so a descriptive name such as `pressure-pass-06.zip`
gives the clearest plots.

The script can be run from anywhere, e.g. `scripts/workflow.sh ...` from the
repository folder. It finds `build/` relative to its own location.

### Examples

```bash
# Run everything; output in /path/to/scratch/warTPC/example and example_results
./workflow.sh example.zip /path/to/scratch/warTPC

# The .zip can be left off; state that it is a pressure dataset
./workflow.sh example /path/to/scratch/warTPC --kind pressure

# Analysis only, no plots
./workflow.sh example.zip /path/to/scratch/warTPC --no-plot

# Only the charge analysis (e.g. to redo it after optical has already run)
./workflow.sh example.zip /path/to/scratch/warTPC --run charge
```

## What it does

| Step | Action | Stops with |
|---|---|---|
| 0 | If the data is already unzipped, uses it and skips steps 1–3 | — |
| 1 | Checks that `/storage/phsccs_grp` and `transfer/` can be read | `no access to the data` |
| 2 | Checks that the ZIP exists in `transfer/` | `<name> does not exist` |
| 3 | Tests the ZIP, checks free space, and unzips into `<output_dir>/<name>/` | `<name> is damaged or not a ZIP file`, `not enough space in ...`, `<name> has no optical/ or charge/ folder` |
| 4 | Runs `optical`, then `charge` (or only the one chosen with `--run`), into `<output_dir>/<name>_results/` | Doesn't stop: failed runs are reported and the next step still runs |
| 5 | Runs `plot` into `<output_dir>/<name>_results/plots/` (unless `--no-plot`) | Doesn't stop |

Notes on step 3:
- The dataset folder can be the top level of the ZIP, or a single folder
  inside it. Either way it ends up as `<output_dir>/<name>/`, named after the
  ZIP.
- The `__MACOSX/` folder that ZIPs made on a Mac contain is removed.
- Extraction happens in a temporary folder first, so a failed unzip leaves
  nothing behind.
- If `<output_dir>/<name>/` already exists, it is reused (step 0). Delete
  that folder to force a fresh unzip.

The original ZIP and the unzipped dataset are never modified. All analysis
output goes to `<output_dir>/<name>_results/`.

## Output

```
<output_dir>/
├── <name>/                      unzipped dataset (optical/, charge/)
└── <name>_results/
    ├── optical/<run>/           Blackbox optical output per run (output.hdf5, integral.csv, plots,
    │                            diagnostics/ with the 2D map and projections from before the fit)
    ├── optical/results/         signals.csv for all runs
    ├── charge/<run>/            Blackbox charge output per run (waveforms.root, signal.csv, plots)
    ├── charge/results/          signals.csv for all runs
    ├── logs/
    │   ├── workflow_<timestamp>.log   everything this script printed (unzip, optical, charge, plot)
    │   ├── optical_<timestamp>.log    whole optical step
    │   ├── charge_<timestamp>.log     whole charge step
    │   ├── optical/<run>.log          one data run, ending in "# result: OK" or "FAILED"
    │   └── charge/<run>.log
    ├── optical_status.txt       runs that failed in optical
    ├── charge_status.txt        runs that failed in charge
    └── plots/                   PLOT_GUIDE plots and tables (see below)
```

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
| `2D_ToT_before_fit.png` | Integrated ToT map before the 2D Gaussian fit, linear and log colour scale; `+` marks the hottest pixel | Every run |
| `xy_projections_before_fit.png` | Raw X and Y projections (summed ToT per column / row) before any fit or background subtraction, linear and log y | Every run |
| `2D_integrated_ToT.png` | Final ToT image with the fit contours and the signal/sideband lines | Runs where the 2D fit worked |
| `x_projection_before_subtraction.png`, `y_projection_before_subtraction.png` | Full projection with the sideband points and the fitted polynomial background, i.e. just before subtraction | Runs where the 2D fit worked |
| `x_projection_signal.png`, `y_projection_signal.png` | Projection after background subtraction | Runs where the 2D fit worked |
| `combined_integral_distribution.png` | Combined signal-integral distribution | Runs where the 2D fit worked |
| `ToT_summary.txt` | Hits, pixels hit, total ToT, and the hottest pixel's share | Every run |
| `fit_parameters.txt` or `fit_failed.txt` | 2D fit result with warning flags, or the reason it failed | Every run |

The fit-dependent plots use the `2nd_degree` background and the `4to8`
signal/sideband setting.

The originals, including all other settings, are in `optical/<run>/`:
- before the fit: `diagnostics/ToT-image-raw.png`, `diagnostics/projections-raw.png`
  (numbers in `projections-raw.csv`, maps in `perChipTOT.npy`, `perChipHIT.npy`)
- after the fit: `signal-integral_x|y/<degree>/<signal>to<sideband>/`, with
  `ToT-image.png`, `<s>to<b>.png` (before subtraction) and `<s>to<b>_signal.png`
  (after)

To list them all:
```bash
find <output_dir>/<name>_results -name '*.png' -path '*optical_per_run*'
```

**If a run failed:** its folder has only the "every run" files. Look at
`fit_failed.txt` and the two before-fit plots to see why, e.g. a single hot
pixel holding most of the ToT, or no clear light spot.

To view them on a Mac, run this in a Mac terminal:
```bash
scp -r hammer:<path to>/<name>_results/plots/optical_per_run ~/Desktop/
```

## Logs

| Log | Contents | On re-run |
|---|---|---|
| `logs/workflow_<timestamp>.log` | Everything the script printed from the unzip step on, the same as the terminal | New file each time |
| `logs/optical_<timestamp>.log`, `logs/charge_<timestamp>.log` | The whole optical / charge step, with a summary of failed runs at the end | New file each time |
| `logs/optical/<run>.log`, `logs/charge/<run>.log` | One data run's output, ending in `# result: OK` or `# result: FAILED` | Rewritten |

Errors from the first two checks (`no access to the data`, `<name> does not
exist`) appear only in the terminal, because they stop the script before any
output folder is created.

If you leave a long run going, you can follow it from another terminal:
```bash
tail -f <output_dir>/<name>_results/logs/workflow_*.log
```

## Exit status and checking the results

- `0`: every step and every run succeeded.
- `1`: something failed or is missing. The last line says
  `Workflow finished with failures`.
- `2`: wrong usage, for example a missing ZIP name or output folder.

After a run, check these files in this order:
1. `optical_status.txt` and `charge_status.txt`: which runs failed. Each
   failed run's own log, `logs/optical/<run>.log` or `logs/charge/<run>.log`,
   shows why.
2. `plots/status.txt`: missing inputs, for example no `pulseheights.csv`.
3. `plots/warnings.txt`: settings-ID mismatches and clipped error bars.
4. `plots/comparisons/notes.csv`: excluded and provisional points.

## Data that is already unzipped

The script never unzips the same data twice. Before checking the storage or
the ZIP, it looks for data that is already unzipped:

1. **`<output_dir>/<name>/` from an earlier run.** Rerun the same command and
   it goes straight to the analysis:
   ```bash
   ./workflow.sh example.zip /path/to/scratch/warTPC --run charge
   ```
2. **A dataset folder given directly** instead of a ZIP name (any folder with
   `optical/` and/or `charge/`). It is used where it is, not copied, and
   results go to `<output_dir>/<folder name>_results/`:
   ```bash
   ./workflow.sh ~/warTPC/pressure-pass-05 /path/to/scratch/warTPC
   ```

In both cases the storage-access check, the ZIP check and the unzip are
skipped, so this works even if the ZIP has been removed from `transfer/` or
the storage isn't mounted. The workflow log shows
`Already unzipped, using the data in ...`.

The script doesn't notice if a ZIP was re-uploaded with new contents. To
unzip again, delete `<output_dir>/<name>/` first.

If `<output_dir>/<name>/` exists but has no `optical/` or `charge/` folder, the
script stops rather than overwrite it.

## Running only optical or only charge

`--run optical` or `--run charge` runs just that analysis. The plots are made
from whatever is in the results folder, so:
- after `--run optical` alone, the V50 and ratio plots are empty (no charge
  results yet);
- running the other one later, into the same `<output_dir>`, adds its results,
  and the plots are remade with both. The step that isn't rerun keeps its
  earlier results.

## Re-running

- **Same ZIP, same `<output_dir>`:** the dataset is reused. Optical and charge
  overwrite their earlier results, and the plots are remade.
- **To keep earlier results,** use a different `<output_dir>`.
- **To compare with an earlier pass,** run `build/plot` yourself with
  `--compare <earlier results>/plots`.

## Environment variables

| Variable | Default | Use |
|---|---|---|
| `WARTPC_STORAGE` | `/storage/phsccs_grp` | Group storage to check |
| `WARTPC_TRANSFER` | `$WARTPC_STORAGE/transfer` | Folder holding uploaded ZIPs |
| `WARTPC_BUILD` | `<repo>/build` | Where `optical`, `charge` and `plot` are |
| `WARTPC_BLACKBOX` | `<repo>/blackbox` | Blackbox scripts and `tpx3dump` to use, e.g. `~/warTPC/Blackbox` |
| `BLACKBOX_SETUP` | bundled `setup_blackbox.sh` | Environment script that loads the Python/ROOT modules |
| `WARTPC_PYTHON` | `python3` | Python used by `plot` |

For example:

```bash
WARTPC_BLACKBOX=~/warTPC/Blackbox ./workflow.sh example.zip /path/to/scratch/warTPC
```

## Common problems

| Message | What to do |
|---|---|
| `no access to the data` | You're not in the group that owns `/storage/phsccs_grp`, or the storage isn't mounted on this node. Check with `ls /storage/phsccs_grp/transfer` and `groups` |
| `<name> does not exist` | Check the spelling with `ls /storage/phsccs_grp/transfer`, and check that the upload has finished |
| `.../build/optical not found` | Build the project (see [Before the first run](#before-the-first-run)) |
| `not enough space in ...` | Choose an `<output_dir>` on scratch or project space |
| `has no optical/ or charge/ folder` | The ZIP has a different layout. It needs `optical/<run>/` and/or `charge/<run>/`, either at the top or inside one folder |
| `contains more than one dataset folder` | Upload each dataset as its own ZIP |
| `charge requested, but <name> has no charge/ folder` (or `optical`) | The ZIP has no data for the analysis chosen with `--run`. Check the ZIP contents, or use `--run both` |
