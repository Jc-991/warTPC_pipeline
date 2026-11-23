# warTPC pipeline

Automation for the Warwick TPC optical (Timepix3) and charge (waveform) analysis.
Every tool here runs on a dataset without modifying it. Results always go to a
separate output folder.

## Choose a workflow

| Task | Entry point | Guide |
|---|---|---|
| Extract a dataset ZIP | `scripts/unzip.sh` | [Unpacking and running a dataset](scripts/workflow.md#unzipsh) |
| Analyse a dataset and generate plots | `scripts/workflow.sh` | [Dataset workflow](scripts/workflow.md#workflowsh) |
| Rerun selected optical runs | `scripts/optical-analysis.sh` | [Selected optical runs](scripts/workflow.md#optical-analysissh-chosen-runs-only) |
| Run optical, charge, or plotting individually | `build/optical`, `build/charge`, `build/plot` | [Analysis commands](#charge--optical) and [plotting guide](PLOT_GUIDE.md) |
| Run the optical and V50 study with historical comparisons and the Fig. 26 overlay | `run_analysis` | [Full-study pipeline](#run_analysis-full-pipeline) and [analysis notes](START_HERE.txt) |

## Folder layout

```
warTPC_pipeline/
├── README.md
├── START_HERE.txt          detailed notes for run_analysis
├── run_analysis            entry point for the full pipeline
├── PLOT_GUIDE.md           which plots and tables each dataset needs
├── CMakeLists.txt          builds the charge, optical and plot commands
├── src/runner.cpp          source for charge and optical
├── src/plot.cpp            launcher for plot
├── plotting/plot.py        the plotting code behind plot
├── scripts/unzip.sh        unzip an uploaded ZIP into a data folder
├── scripts/workflow.sh     analyse an unzipped dataset: optical, charge, plots
├── scripts/optical-analysis.sh  optical analysis of chosen runs only
├── scripts/workflow.md     usage and troubleshooting for the scripts above
├── pipeline/pipeline.py    full optical + V50 pipeline
├── reference/
│   ├── history.csv             comparison baseline (earlier voltage runs, pressure passes 1–5)
│   └── figure26_reference.png  calibrated 2750x2000 Fig. 26 image for the overlay
└── blackbox/               Blackbox scripts and tools (kept together, see below)
    ├── optical_run.sh, charge_run.sh, blackbox1.sh
    ├── setup_blackbox.sh       loads the cluster modules
    ├── tpx3dump                TPX3 -> HDF5 converter (Linux x86-64 binary)
    ├── optical-analysis.py
    ├── waveform-integrator.py
    └── waveform-plotting.py
```

The files in `blackbox/` must stay in one folder: the shell scripts call
`./tpx3dump` and `python3 <script>.py` relative to where they run.

## Dataset format

```
<dataset>/
├── optical/<run>/   rawdata_000000.tpx3, settings.csv
└── charge/<run>/    waveforms.csv, settings.csv, pulseheights.csv
```

`charge_run.sh` processes `waveforms.csv`. `plot` and `run_analysis` read
`pulseheights.csv` for V50. No Blackbox script creates that file, so it must
already be in the dataset.

## Requirements

The analysis needs the Warwick cluster (hammer) environment:

- Linux x86-64, because `tpx3dump` is a Linux binary
- Python 3 with ROOT, numpy, pandas, scipy, h5py and matplotlib. On the cluster,
  `blackbox/setup_blackbox.sh` loads the modules.
- CMake ≥ 3.16 and a C++17 compiler, to build `charge`, `optical` and `plot`
- `plot` itself needs only numpy, scipy, matplotlib and Pillow (no ROOT)

Run analyses inside an authorised compute allocation, not on a login node.

## Whole workflow: scripts/unzip.sh + scripts/workflow.sh

For a ZIP uploaded to `/storage/phsccs_grp/transfer/`: unzip it once with
`unzip.sh`, then analyse the folder with `workflow.sh` as often as needed. Full
usage, output and troubleshooting are in [scripts/workflow.md](scripts/workflow.md).

```bash
cd scripts
./unzip.sh example.zip ~/warTPC/data                                   # -> ~/warTPC/data/example/
./workflow.sh ~/warTPC/data/example ~/warTPC/results                   # optical, charge, plots
./workflow.sh ~/warTPC/data/example ~/warTPC/results --no-plot         # same without the plots
./workflow.sh ~/warTPC/data/example ~/warTPC/results --run charge      # only charge (or --run optical)
./optical-analysis.sh ~/warTPC/data/example ~/warTPC/results --runs 2,5-7  # redo chosen optical runs
```

`unzip.sh`:
1. For a bare ZIP name, checks that `/storage/phsccs_grp` and `transfer/` can
   be read. If not, it prints `no access to the data` and stops.
2. Checks that the ZIP exists. If not, it prints `<name> does not exist`.
3. Tests the ZIP and the free space, and unzips it into `<data_dir>/<name>/`.
   If that folder already holds the data, it does nothing (`--force` unzips
   again).

`workflow.sh` (never unzips; give it the unzipped folder):
1. Runs `optical` and `charge` into `<output_dir>/<name>_results/`.
2. Runs `plot` into `<output_dir>/<name>_results/plots/` (see [plot](#plot)).

Everything `workflow.sh` prints is also saved to
`<output_dir>/<name>_results/logs/workflow_<timestamp>.log`.

`<name>` is the dataset folder's name (the ZIP name without `.zip`), and it's
used as the dataset name in plots. Add `--kind pressure` or `--kind voltage`
if the name doesn't start with `pressure-pass`, `prp`, `voltage-run` or `vr`.
Build the project first (see below).

## charge / optical

### Build

Build on the cluster. 

```bash
cd path/to/directory/warTPC_pipeline
cmake -S . -B build
cmake --build build
```

To install the commands somewhere else (optional):

```bash
cmake --install build --prefix path/to/directory/tools
# -> path/to/directory/tools/bin/{charge,optical,plot}
#    path/to/directory/tools/share/wartpc/  (copy of blackbox/, plotting/, reference/)
```

### Run

```bash
build/optical -i path/to/directory/pressure-pass-05 -o path/to/directory/results/pp05
build/charge  -i path/to/directory/pressure-pass-05 -o path/to/directory/results/pp05
```

| Option | Meaning |
|---|---|
| `-i, --input DIR` | Dataset folder (must contain `optical/` or `charge/`) |
| `-o, --output DIR` | Output folder. Created if missing; must be outside the dataset |
| `--blackbox DIR` | Use the scripts and tools in `DIR` instead of the bundled ones (also `WARTPC_BLACKBOX`) |
| `--setup FILE` | Source this environment script first (also `BLACKBOX_SETUP`). By default, `setup_blackbox.sh` is sourced automatically when a module system is present |
| `--no-setup` | Don't source any environment script |
| `-h, --help` | Show help |

### What it does

1. **Mirrors the dataset into the output folder.** The Blackbox scripts write
   their results into whatever dataset they're given, so the command builds a
   mirror of it in the output folder:
   - Large raw inputs (`*.tpx3`, `waveforms.csv`) are symlinked.
   - Small files such as `settings.csv` are copied.
   - Previously generated outputs (`output.hdf5`, `waveforms.root`, result
     subfolders) are skipped, so nothing can be written back into the original
     data.
2. **Runs the unchanged script** on the mirror, from a private working folder
   (`<output>/.blackbox/`).
3. **Logs everything.** Output appears in the terminal and is saved twice:
   - `<output>/logs/<mode>_<timestamp>.log` holds the whole invocation. A new
     file is made each time, so earlier logs are kept.
   - `<output>/logs/<mode>/<run>.log` holds one data run, ending with
     `# result: OK` or `# result: FAILED`. These are rewritten on each
     invocation.
4. **Checks each run.** The scripts' own exit code isn't reliable, so a run
   counts as done only if it produced `integral.csv` (optical) or `signal.csv`
   (charge). Failed runs are listed at the end and in
   `<output>/<mode>_status.txt`, and the command exits with status 1 if any run
   failed.

### Output

```
<output>/
├── optical/<run>/        output.hdf5, integral.csv, signal-integral_x|y/ plots,
│                         diagnostics/ (ToT map before the 2D fit, fit result or error)
├── optical/results/      signals.csv, signals_inspect.csv (one row per run)
├── charge/<run>/         waveforms.root, signal.csv, p1/, cut folders
├── charge/results/       signals.csv, signals_inspect.csv
├── logs/                 <mode>_<timestamp>.log per invocation,
│                         <mode>/<run>.log per data run
├── optical_status.txt
└── charge_status.txt
```

Running the same mode again into the same output folder replaces that mode's
earlier results, as the Blackbox scripts do. Use a new `-o` to keep them.

`charge_run.sh` takes its list of runs from the `optical/<run>` folder names.
The command keeps that behaviour, so a run that exists only under `charge/` is
not processed. If the dataset has no `optical/` folder, the `charge/` run names
are used instead.

## plot

Run it after `optical` and/or `charge`, on their output folder:

```bash
build/plot -i path/to/directory/results/pressure-pass-05 -o path/to/directory/plots/pressure-pass-05
```

The dataset name used in legends and comparisons is the `-i` folder name. A
name starting with `pressure-pass` or `voltage-run` also sets the marker type.
For any other folder name, pass `--dataset` and `--kind`.

| Option | Meaning |
|---|---|
| `-i, --input DIR` | Output folder of `optical` / `charge` (an original dataset also works; then only V50 is available) |
| `-o, --output DIR` | Folder for plots and tables. Rerunning replaces the plots in it |
| `--dataset NAME` | Dataset name for legends and comparisons (default: input folder name) |
| `--kind pressure\|voltage` | Marker type (default: guessed from dataset or run names) |
| `--exclude RUNS` | Comma-separated runs left out of summary and comparison plots (default `prp2-04,prp3-04`; `''` for none) |
| `--compare DIR ...` | Earlier `plot` output folders to add to the comparisons |
| `--history FILE` | Comparison baseline (default `reference/history.csv`) |
| `--paper-overlay FILE`, `--no-paper` | Fig. 26 image to overlay, or skip it |
| `--rms-flag-percent N` | Flag optical results whose RMS is above N% of S_O (default 10) |
| `--setup FILE`, `--no-setup` | Environment script, as for `charge`/`optical` |

Set `WARTPC_PYTHON` to choose the Python interpreter (default `python3`).

### Output

```
<plot_dir>/
├── run_conditions.csv/.md   V0–V4, pressure, methane fraction, exposure, V43+21/P, ID mismatches
├── results.csv              S_O, RMS, V50, width, event counts, ratio, review flags per run
├── optical_per_run/<run>/   2D_ToT_before_fit.png and xy_slices_before_fit.png only
│                            (made before the fits, so present for every run)
├── v50_distributions/       one histogram per run, with peak estimate, bin width and counts
├── summary_plots/           optical and V50: streaming + physics, linear + log;
│                            ratio: streaming + physics, linear
├── comparisons/             optical, V50 and ratio physics plots against earlier scans/passes,
│                            Fig. 26 paper overlay, paper_overlay_out_of_range.csv,
│                            notes.csv (excluded, provisional and off-axis points)
├── README.txt               methods: what each error bar represents
├── warnings.txt             ID mismatches, clipped error bars
└── status.txt               missing or failed inputs
```

Plot conventions follow `PLOT_GUIDE.md`:
- Hollow squares are pressure runs and solid circles are voltage runs.
- A black × marks a point with a review flag; the reason is in `comparisons/notes.csv`.
- Linear plots stop at 1.1 × the largest central value, and the title says when
  an error bar is clipped.

For comparisons, a dataset's results replace its rows in `history.csv`. Add a
new pass to the baseline either by passing its plot folder with `--compare` or
by appending its rows from `results.csv` to `reference/history.csv`.

V50 uses the same peak finder as `run_analysis`, so values are comparable with
`history.csv`.

### Why did an optical run fail?

`blackbox/optical-analysis.py` saves diagnostics in `optical/<run>/diagnostics/`
**before** the 2D Gaussian fit, so they exist even when the run fails later.
These copies are made by this project's `blackbox/` version only, not by the
original Blackbox.

| File | Contents |
|---|---|
| `ToT-image-raw.png` | The integrated ToT map (linear colour scale); `+` marks the hottest pixel, where the fit starts |
| `ToT-image-projections.png` | The ToT map with the X slice through the peak (pixel row) above and the Y slice (pixel column) to the right, on shared pixel axes; linear scale |
| `projections-raw.png`, `projections-raw.csv` | The X and Y slices through the peak as histograms, before any fit or background subtraction; the CSV also has the full row/column sums |
| `summary.txt` | Hits, pixels hit, total ToT, and the hottest pixel's share of the total (a large share means a hot pixel) |
| `perChipTOT.npy`, `perChipHIT.npy` | The 256×256 ToT and hit-count maps, for `np.load` |
| `fit_parameters.txt` | Fit result with uncertainties, plus flags: non-finite values, centre off the chip, width under half a pixel or over half the chip |
| `fit_failed.txt` | The fit's error message and starting values, if it failed |
| `*-rebin<N>.*` | With `WARTPC_REBIN=N` (or `optical-analysis.sh --rebin N`): the map and slices after merging N×N pixels; the 2D fit then runs on that map and its result is converted back to pixel units |
| `sideband_regions/<s>to<b>.png`, `sideband_regions/regions.csv` | After the 2D fit, before the sideband fit: X and Y projections with the signal region and the sideband points for each of the 10 settings, and a table flagging impossible regions |
| `sideband_failed.txt` | Which sideband setting crashed, and the error |
| `no_hits.txt` | Written if the HDF5 file has no pixel hits |

`plot` copies `ToT-image-raw.png` and `projections-raw.png` into
`optical_per_run/<run>/` (as `2D_ToT_before_fit.png` and
`xy_slices_before_fit.png`) and lists the failure reasons in `status.txt`.

## run_analysis (full pipeline)

```bash
chmod +x path/to/directory/warTPC_pipeline/run_analysis
path/to/directory/warTPC_pipeline/run_analysis path/to/directory/pressure-pass-05 \
  --blackbox path/to/directory/Blackbox \
  --results  path/to/directory/analysis_results
```

- The first argument can be an extracted dataset folder or a ZIP.
- Each invocation creates a new folder, `<results>/<dataset>_<timestamp>/`,
  containing `results.csv`, `status.txt`, `warnings.txt`, `summary_plots/`,
  `optical_per_run/`, `v50_distributions/`, `comparisons/`, `logs/` and `work/`.
- Useful options:
  - `--exclude` (default `prp2-04,prp3-04`; `''` includes everything)
  - `--reuse-hdf5`
  - `--paper-overlay`

For the V50 method, uncertainty treatment and the meaning of review flags, see
`START_HERE.txt`. Update `reference/history.csv` if earlier results change.

## Status

- `charge` and `optical` have been tested with stub tools on a Mac.
- `plot` has been tested on a simulated result folder on a Mac.
- `scripts/unzip.sh` has been tested on a Mac against fake storage: no access,
  a missing file, a damaged ZIP, a ZIP with `__MACOSX/`, already unzipped, and
  `--force`. `scripts/workflow.sh` has been tested on unzipped fake data.
- `run_analysis` has been tested on simulated input.
- `optical` and `scripts/workflow.sh` have run on a real voltage dataset on the
  cluster. Check the logs and status files before using the results.
