# VR22 optical spark study checkpoint

24 November 2026

The spark-removal trial for `vr22-07` is complete. The pipeline exports the pre-tagging ToT-versus-time spectrum and the four classic optical plots. The eight-run Hammer batch finished, and the report flagged missing X-projection pairs for `vr22-11` through `vr22-13`. The comparison will address whether the double structure in the X projection persists after the cut.

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

These were hit-rate candidates from the earlier time-window cut. That cut used 10 ms bins, a local median, and margins of 10 ms before and 50 ms after flagged bins. The 351 intervals are distinct from the current high-ToT spark count.

The trial report is at `~/warTPC/results/vr22-07-spark-removed/voltage-run-22-11-2026_results/optical/vr22-07/diagnostics/spark_status.txt` on Hammer.

## Pipeline and deliverables

- `WARTPC_SPARK_MODE=off` keeps all hits. `detect` reports how many hits exceed the run's all-hit mean ToT + 10 RMS. `remove` masks only those individual hits before building the fit maps. Exposure stays unchanged and the HDF5 remains intact.
- The spectrum plots per-hit ToT (Z) against arrival time since the first hit (t), with colour showing hit count. It uses all original hits before tagging. In `detect` and `remove` modes it is saved under `optical/<run>/diagnostics/` and copied into `plots/optical_per_run/<run>/`.
- Each completed run’s summary includes the 2D ToT image, combined integral distribution, and the background-subtracted X and Y projections. Additional X/Y plots are opt-in with `WARTPC_SIGNAL_PLOTS=1`.
- [The report script](../../scripts/report-vr22-sparks.py) packages ten figures per run, including separate before and after versions of the X projection, Y projection, and combined integral distribution.

## Workflow checklist

- [x] Write one `run_summary.txt` for each completed optical run. With plotting enabled, it appears at `plots/optical_per_run/<run>/run_summary.txt`. With `--no-plot`, it is available at `optical/<run>/run_summary.txt`.
- [x] Include `S_O^norm = S_O / exposure_after_spark_removal` and the eight agreed columns for run ID, optical signal, original exposure, spark count, algorithm iterations, exposure removed, usable exposure, and normalized signal.
- [x] Verify the workflow with two synthetic runs. Each plot folder received its own text summary.
- [x] Package the actual `vr22-06` and `vr22-07` values into their separate Desktop summaries. The ToT cut used one pass and removed zero exposure from both runs. The spark count now matches the marked-up removed-hit count: 2 for run 6 and 0 for run 7.
- [ ] Verify automatic text-summary output on Hammer after deploying the updated workflow.

## Resume on Hammer

Use the same X-rebin setting in both passes to isolate the spark cut. The commands below use the original X binning. Run from the updated pipeline checkout in a compute allocation.

```bash
source blackbox/setup_blackbox.sh
dataset="$HOME/warTPC/data/voltage-run-22-11-2026"
base="$HOME/warTPC/results/vr22-spark-study-tot10rms"
runs="vr22-06,vr22-07,vr22-08,vr22-09,vr22-10,vr22-11,vr22-12,vr22-13"

WARTPC_SPARK_MODE=off bash scripts/optical-analysis.sh \
  "$dataset" "$base/before" --runs "$runs" --rebin-x off

WARTPC_SPARK_MODE=remove bash scripts/optical-analysis.sh \
  "$dataset" "$base/after" --runs "$runs" --rebin-x off

python3 scripts/report-vr22-sparks.py \
  "$base/before/voltage-run-22-11-2026_results" \
  "$base/after/voltage-run-22-11-2026_results" \
  "$base/report"
```

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

The initial Hammer report is at `~/warTPC/results/vr22-spark-study/report/`. Its after-removal batch log is `after/voltage-run-22-11-2026_results/logs/optical-analysis_20261124-162148.log` under that study directory. The earlier burst-grouping counter reported 0, 4, 3, 5, 4, 9, 15, and 24 for runs 06–13 respectively. The current summary counts individual hits above the removal threshold.
