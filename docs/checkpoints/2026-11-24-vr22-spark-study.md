# VR22 optical spark study checkpoint

Started 24 November 2026. Updated 26 November 2026.

## Current workflow

- Before and after fits use the same X binning. X rebinning defaults to off.
- Time zero is the first stored hit. Matt’s original exposure convention is `(toa[-1] - toa[0]) / 1e13` seconds. The ToT-versus-time plot uses the same origin and scale as spark grouping, with 10 ms bins for the background colours.
- The cut uses **5 ms of detector time** per window. It sums ToT in each occupied window, flags sums strictly above the grouped mean plus 10 standard deviations, and removes all hits in those windows. The summary counts flagged windows and subtracts their overlap with the run from exposure. The HDF5 retains the original hits.
- A complete per-run export contains nine PNGs and two text summaries. The plots include before/after X and Y projections and combined integral distributions, the after-cut 2D ToT image, the grouped ToT histogram, and the arrival-time plot with removed hits marked. With an incomplete export the workflow publishes available pairs and retains the work directory.
- `run_summary.txt` has a tab-separated header and one data row. `run_summary_readable.txt` shows one field per line. Both use seconds for exposure and absolute decimal fractions for removed exposure and relative optical RMS, where 1 = 100%.
- Spark count and removed-exposure fraction each have a streaming plot by run order, a physics plot against V/P, and a dataset overlay. The VR22 overlay has one series because the reference data has no spark measurements.

## Latest full Hammer run

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
  -i "$HOME/warTPC/data/voltage-run-22-11-2026" \
  -o "$HOME/warTPC/results/full-vr22-optical-$(date +%Y%m%d-%H%M%S)" \
  --run optical
```

Transfer the resulting `plots/` directory for the per-run plots and summaries, streaming and physics plots, and overlays. It contains no HDF5 files.

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
