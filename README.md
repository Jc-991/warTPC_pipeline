# warTPC pipeline

Automation for the Warwick TPC optical (Timepix3) and charge (waveform) analysis.
Every tool here runs on a dataset without modifying it. Results always go to a
separate output folder.

There are two ways to run an analysis:

| Command | What it runs | Use it for |
|---|---|---|
| `build/optical`, `build/charge` | The Blackbox `optical_run.sh` / `charge_run.sh`, unchanged | Running the standard Blackbox analysis on a dataset |
| `run_analysis` | `pipeline/pipeline.py`: optical + V50 analysis, summary plots, comparisons | The full study: S_O, V50, S_O/V50 against V/P, historical comparison, Fig. 26 overlay |

`START_HERE.txt` describes `run_analysis` in full, including its physics
conventions and caveats.

## Folder layout

```
warTPC_pipeline/
├── README.md
├── START_HERE.txt          detailed notes for run_analysis
├── run_analysis            entry point for the full pipeline
├── CMakeLists.txt          builds the charge and optical commands
├── src/runner.cpp          source for both commands
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

`charge_run.sh` processes `waveforms.csv`. `run_analysis` reads
`pulseheights.csv` for V50.

## Requirements

The analysis needs the Warwick cluster (hammer) environment:

- Linux x86-64, because `tpx3dump` is a Linux binary
- Python 3 with ROOT, numpy, pandas, scipy, h5py and matplotlib. On the cluster,
  `blackbox/setup_blackbox.sh` loads the modules.
- CMake ≥ 3.16 and a C++17 compiler, to build `charge` and `optical`

Run analyses inside an authorised compute allocation, not on a login node.

## charge / optical

### Build

Build on the cluster. A binary built on a Mac will not run there.

```bash
cd ~/warTPC/warTPC_pipeline
cmake -S . -B build
cmake --build build
```

To install the commands somewhere else (optional):

```bash
cmake --install build --prefix ~/warTPC/tools
# -> ~/warTPC/tools/bin/{charge,optical}
#    ~/warTPC/tools/share/wartpc/  (copy of blackbox/)
```

### Run

```bash
build/optical -i ~/warTPC/pressure-pass-05 -o ~/warTPC/results/pp05
build/charge  -i ~/warTPC/pressure-pass-05 -o ~/warTPC/results/pp05
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
3. **Logs everything.** Output appears in the terminal and is saved to
   `<output>/logs/<mode>_<timestamp>.log`.
4. **Checks each run.** The scripts' own exit code isn't reliable, so a run
   counts as done only if it produced `integral.csv` (optical) or `signal.csv`
   (charge). Failed runs are listed at the end and in
   `<output>/<mode>_status.txt`, and the command exits with status 1 if any run
   failed.

### Output

```
<output>/
├── optical/<run>/        output.hdf5, integral.csv, signal-integral_x|y/ plots
├── optical/results/      signals.csv, signals_inspect.csv (one row per run)
├── charge/<run>/         waveforms.root, signal.csv, p1/, cut folders
├── charge/results/       signals.csv, signals_inspect.csv
├── logs/                 one log per invocation
├── optical_status.txt
└── charge_status.txt
```

Running the same mode again into the same output folder replaces that mode's
earlier results, as the Blackbox scripts do. Use a new `-o` to keep them.

`charge_run.sh` takes its list of runs from the `optical/<run>` folder names.
The command keeps that behaviour, so a run that exists only under `charge/` is
not processed. If the dataset has no `optical/` folder, the `charge/` run names
are used instead.

## run_analysis (full pipeline)

```bash
chmod +x ~/warTPC/warTPC_pipeline/run_analysis
~/warTPC/warTPC_pipeline/run_analysis ~/warTPC/pressure-pass-05 \
  --blackbox ~/warTPC/Blackbox \
  --results  ~/warTPC/analysis_results
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
- `run_analysis` has been tested on simulated input.
- Neither has been tested on a real dataset on the cluster. Check the logs and
  status files before using the results.
