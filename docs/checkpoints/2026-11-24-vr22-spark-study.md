# November optical production and spark study checkpoint

Started 24 November 2026. Updated 27 November 2026.

## November production status

- The Desktop export is `~/Desktop/warTPC optical-voltage-pressure/`. It holds voltage scans from 18, 19, 20, and 22 November and pressure passes 01–05. The VR22 dataset was renamed to `voltage-run-22-11-26` on the cluster. The export records 83 run folders and 79 saved optical fits. The optical production overlay plots 76 points.
- The selected production inputs and provenance are in `combined-comparison-full/plots/sources.csv` and `notes.csv` under the Desktop export. The four voltage scans and pressure pass 02 contribute after-cut fits. Pressure pass 05 contributes recovered after-cut fits. Pressure pass 03 contributes recovered before-cut fits for runs 01–03. Passes 01 and 04 contribute older saved optical fits with unverified spark-cut status.
- No usable fit was exported for `prp1-05`, `prp3-04`, `prp4-04`, or `prp5-20`. The comparison retains the prior exclusion of `prp2-04` and omits `prp5-18` and `prp5-19` because their optical fit RMS exceeds the signal. The latter two were omitted from every plot in the current combined comparison. On C01, black crosses mark `prp1-01` (26.4% relative optical RMS) and `vr22-12` (11.4%) for review. Both points are retained.
- The production spark count and exposure-fraction plots have 66 points. The X/Y, normalized background, and signal-to-background plots have 69 each. Passes 01 and 04 lack the newer observables. Pass 03 has before-cut position and background values without spark counts or removed fractions. Missing values are unavailable measurements.
- The verified before-cut overlays use **49 runs** from the four voltage scans and pressure passes 02 and 03. **46 of those runs** also have verified after-cut fits, with the existing exclusions applied. The before-cut signal plot uses a symmetric log axis to retain negative fit estimates. C14, the production background overlay, uses a log y-axis. The before-cut PNGs were reproduced with their original appearance and embedded generation time, source paths, modification times, and checksums in `combined-comparison-full/plots/before-cut-20261126-233423/`.

## Current analysis and export workflow

- `scripts/workflow.sh` writes per-run plots, dataset streaming and physics plots, and tables. It no longer generates multi-dataset comparisons. The top-level `plots/run_summary.txt` aggregates the available per-run TSV summaries in run order. The final workflow packaging step rebuilds it from the published per-run files.
- `scripts/compare-optical-results.sh` builds comparisons from explicitly selected exports. Repeat `-i PATH` for each `plots/` folder or `results.csv`, and use `-o` for a new or empty directory. Streaming, physics panels, overlays, and Figure 26 are on by default. Reproduce the current compact labels and omissions with `--compact-labels --exclude-runs prp5-18,prp5-19`. Use `--historical-charge` to fill missing V50 and optical/V50 only from matching historical runs. Figure 26's bundled image already contains older November markers. A plain overlay shows the selected numerical results directly.
- Main comparison IDs are C01 for normalized optical signal, C05/C07 for X/Y positions, C11/C12 for spark count and removed exposure fraction, C13 for signal-to-background, and C14 for normalized background. Corresponding streaming IDs are S05/S09 for X/Y, S17/S19 for sparks and exposure fraction, S27 for signal-to-background, and S29 for background. Use source tables to establish each plot's coverage.
- Each standard X/Y position uses positive residual ToT as the weight at each pixel coordinate. The reported RMS measures the profile width in pixels. The signal comes from first fitting the background curve, subtracting it, and summing the residual bins. The reported background integral for each fit is then total ToT minus signal. Signal and background are reported in ms of summed ToT and normalized by exposure in seconds. Fit spreads use 60 variations across the two axes, three polynomial degrees, and ten window settings. The reported S/B error assumes independent signal and background spreads.

## Presentation and findings

- The user-edited presentation is `~/Desktop/jyan_20261126_warTPC_raw_data_summary.pptx`. The reference notes are `~/Desktop/November spark study - calculations and observations.pdf`. Five pressure run-condition PNGs are in `~/Desktop/voltage_run_conditions/` alongside the voltage tables.
- Run 7 is the worked example. The cut flagged **five 5 ms windows**, removed **231,465 of 499,119 hits (46.4%)**, and excluded **25 ms of 189.988 s (0.0132%)**. The red circles are individual removed hits. They form two visible groups near 26 s and 97 s. The full-run display cannot resolve how the five windows are split between the groups. Use the `Candidate since first hit (s)` rows in its cluster `spark_status.txt` for the exact split.
- The ToT-versus-arrival-time image used **10 ms** time columns for the run 7 slides; from 27 November it uses **5 ms**, matching the cut, with each pixel showing the largest 5 ms bin it covers. It shows individual hit ToT on the vertical axis. The cut instead sums the hit ToT within **5 ms** arrival-time windows. The grouped histogram's horizontal axis shows those sums, and its vertical axis counts occupied windows in each summed-ToT range. The plot labels the decoder values as stored units. The later conversion to ms treats stored hit ToT as ns, with decoder units still unverified independently.
- Among 46 matched runs, normalized background fell in all 46, with a **74.7% median reduction**. S/B increased in all 46, and the fitted signal increased in 31. The matched pressure evidence is three runs from pass 02. These findings should be presented as results for the matched sample.
- The titles of slides 14 and 16 in the user-edited deck describe the plots as after spark detection and removal. Their embedded files are the production overlays and include before-cut pass 03 points. C01 also includes older saved fits for passes 01 and 04. Use “production overlay using available fits” when describing those figures.

## Deferred pressure refits

- The cluster has `output.hdf5` files under `~/warTPC/data/pressure-pass-NN/optical/<run>/` for the ten selected runs: `prp1-01`–`04`, `prp3-01`–`03`, and `prp4-01`–`03`. The corresponding `settings.csv` files are needed for the fits. Their decoded inputs could be reused through read-only links to bypass `tpx3dump` and clustering.
- The cluster `refit-hdf5-after/plots` outputs reported **zero optical fits** for all three passes. The analysis failure has not been diagnosed. If the user resumes, inspect the existing per-run `refit-hdf5-after/logs/<run>.log` files before retrying. The user explicitly deferred this work.
- The user asked that Codex never initiate a Hammer connection. Give commands for the user to run themselves. The cluster scheduler rejected running from `/home` and requested the user's assigned `/storage` area. No personal storage path has been confirmed.

## Earlier VR22 workflow

- Before and after fits use the same X binning. X rebinning defaults to off.
- Time zero is the first stored hit. Matt’s original exposure convention is `(toa[-1] - toa[0]) / 1e13` seconds. The ToT-versus-time plot uses the same origin and scale as spark grouping, with 5 ms bins for the background colours (10 ms before 27 November).
- The cut uses **5 ms of detector time** per window. It sums ToT in each occupied window, flags sums strictly above the grouped mean plus 10 standard deviations, and removes all hits in those windows. The summary counts flagged windows and subtracts their overlap with the run from exposure. The HDF5 retains the original hits.
- A complete per-run export contains nine PNGs and two text summaries. The plots include before/after X and Y projections and combined integral distributions, the after-cut 2D ToT image, the grouped ToT histogram, and the arrival-time plot with removed hits marked. With an incomplete export the workflow publishes available pairs and retains the work directory.
- `run_summary.txt` has a tab-separated header and one data row. `run_summary_readable.txt` shows one field per line. Both use seconds for exposure and absolute decimal fractions for removed exposure and relative optical RMS, where 1 = 100%.
- Spark count and removed-exposure fraction each have a streaming plot by run order, a physics plot against V/P, and a dataset overlay. The VR22 overlay has one series because the reference data has no spark measurements.

## Earlier full VR22 Hammer run

Results are under `~/warTPC/results/full-vr22-optical-2/voltage-run-22-11-2026_results/`. The Desktop export is at `~/Desktop/VR22 optical results/full-vr22-optical-2/plots/`. Verified both before and after X/Y projections for runs 01–10, after projections for runs 11–13, and all six spark-observable plots in the Desktop export.

- Run 13 decoded successfully in both passes. The uncut Gaussian fit returned a width larger than half the chip. Sideband diagnostics flagged all 20 axis/setting combinations, and ROOT rejected an argument during the fourth-degree X fit at 3–7 sigma. The before pass produced no `integral.csv` or paired fit plots.
- The run 13 after-cut fit completed after removal of 16 flagged windows. Its after projections and combined integral distribution are present.
- The retained before-pass diagnostics are under `.spark-work.LxpEDY/before/optical/vr22-13/diagnostics/` relative to the latest Hammer results. The cause of the missing before fits for runs 11 and 12 has not been confirmed.
- A previous two-run validation with Matt’s timing flagged one 5 ms window for run 6, lowering exposure from 99.9959023781 s to 99.9909023781 s. Its removed-exposure fraction was about 0.000050002.

The open analysis question is whether the double structure in the X projection persists after the cut. Evaluate it for the runs with valid pairs and investigate the missing before-cut fits separately.

## Rerun on Hammer

Run from the updated checkout in a compute allocation. Add `--runs vr22-06,vr22-07` to select only those two runs.

```bash
bash scripts/workflow.sh \
  -i "$HOME/warTPC/data/voltage-run-22-11-26" \
  -o "$HOME/warTPC/results/full-vr22-optical-$(date +%Y%m%d-%H%M%S)" \
  --run optical
```

Transfer the resulting `plots/` directory for the per-run plots and summaries, streaming plots, and physics plots. Run the comparison script separately for overlays. The plot export contains no HDF5 files.

## Initial run 7 hit-rate trial

| Quantity | Result |
|---|---:|
| Candidate intervals after merging | 351 |
| Hits before removal | 499,119 |
| Hits kept | 147,117 |
| Hits excluded | 352,002 (70.5%) |
| Exposure before removal | 189.987624 s |
| Exposure after removal | 163.56 s |
| Exposure excluded | 26.4276245 s (13.9%) |

These were hit-rate candidates from the earlier time-window cut. That cut used 10 ms bins, a local median, and margins of 10 ms before and 50 ms after flagged bins. The 351 intervals are distinct from the current count of flagged 5 ms windows.

The trial report is at `~/warTPC/results/vr22-07-spark-removed/voltage-run-22-11-2026_results/optical/vr22-07/diagnostics/spark_status.txt` on Hammer.

## Initial eight-run hit-rate batch results

The after-removal batch reported eight runs. The report printed the following counts and comparison status.

| Run | Candidate intervals | X projection comparison |
|---|---:|---|
| `vr22-06` | 234 | Pair available |
| `vr22-07` | 351 | Pair available |
| `vr22-08` | 232 | Pair available |
| `vr22-09` | 176 | Pair available |
| `vr22-10` | 163 | Pair available |
| `vr22-11` | 228 | Before plot missing |
| `vr22-12` | 323 | Before plot missing |
| `vr22-13` | 466 | Before plot missing |

The initial Hammer report is at `~/warTPC/results/vr22-spark-study/report/`. Its after-removal batch log is `after/voltage-run-22-11-2026_results/logs/optical-analysis_20261124-162148.log` under that study directory. The earlier burst-grouping counter reported 0, 4, 3, 5, 4, 9, 15, and 24 for runs 06–13 respectively. A later per-hit ToT trial removed 2 hits from run 6 and 0 from run 7, with no exposure excluded. The experimental 5 µs grouped cut subsequently flagged 8 windows for run 6. These counts belong to different cuts.
