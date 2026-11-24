# VR22 optical spark study checkpoint

24 November 2026

The spark-removal trial for `vr22-07` is complete. The pipeline exports the pre-tagging ToT-versus-time spectrum and the four classic optical plots. The eight-run Hammer batch finished, and the report flagged missing X-projection pairs for `vr22-11` through `vr22-13`. The comparison will address whether the double structure in the X projection persists after the cut.

## Run 7 trial

| Quantity | Result |
|---|---:|
| Candidate intervals after merging | 351 |
| Hits before removal | 499,119 |
| Hits kept | 147,117 |
| Hits excluded | 352,002 (70.5%) |
| Exposure before removal | 189.987624 s |
| Exposure after removal | 163.56 s |
| Exposure excluded | 26.4276245 s (13.9%) |

These are hit-rate candidates. A single merged interval can contain several spikes, and the 351 intervals have not been confirmed as physical sparks. The detector uses 10 ms hit-count bins, a local median, and provisional margins of 10 ms before and 50 ms after flagged bins. Given the fraction of hits excluded, check representative bursts and the recovery against the optical data and any synchronized charge or HV records before adopting the cleaned signal.

The trial report is at `~/warTPC/results/vr22-07-spark-removed/voltage-run-22-11-2026_results/optical/vr22-07/diagnostics/spark_status.txt` on Hammer.

## Pipeline and deliverables

- `WARTPC_SPARK_MODE=off` keeps all hits. `detect` reports candidates, and `remove` masks them before building the fit maps and subtracts the excluded duration from the exposure. The HDF5 remains intact.
- The spectrum plots per-hit ToT (Z) against arrival time since the first hit (t), with colour showing hit count. It uses all original hits before tagging. In `detect` and `remove` modes it is saved under `optical/<run>/diagnostics/` and copied into `plots/optical_per_run/<run>/`.
- Each completed run’s summary includes the 2D ToT image, combined integral distribution, and the background-subtracted X and Y projections. Additional X/Y plots are opt-in with `WARTPC_SIGNAL_PLOTS=1`.
- [The report script](../../scripts/report-vr22-sparks.py) produces `run_summary.csv`, `excluded_intervals.csv`, and a plot folder for each run. The summary records candidate counts, exposures, and `S_O_norm` in ms/s. It calculates `S_O` in ms by multiplying `S_O_norm` by the usable exposure. Each excluded interval has its own start, stop, and duration. The X comparison retains the source panels’ axis scales.

## Resume on Hammer

Use the same X-rebin setting in both passes to isolate the spark cut. The commands below use the original X binning. Run from the updated pipeline checkout in a compute allocation.

```bash
source blackbox/setup_blackbox.sh
dataset="$HOME/warTPC/data/voltage-run-22-11-2026"
base="$HOME/warTPC/results/vr22-spark-study"
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

## Eight-run batch results

The after-removal batch reported eight runs. The report printed the following counts and comparison status.

| Run | Candidate intervals | X projection comparison |
|---|---:|---|
| `vr22-06` | 234 | Pair available |
| `vr22-07` | 351 | Pair available |
| `vr22-08` | 232 | Pair available |
| `vr22-09` | 176 | Pair available |
| `vr22-10` | 163 | Pair available |
| `vr22-11` | See CSV | One or both plots missing |
| `vr22-12` | See CSV | One or both plots missing |
| `vr22-13` | See CSV | One or both plots missing |

The report prints an issue in place of the count when a comparison is incomplete. Check `run_summary.csv` for any counts that were recorded for runs 11–13, then check which pass is missing its X plot. The Hammer report is at `~/warTPC/results/vr22-spark-study/report/`. The after-removal batch log is `after/voltage-run-22-11-2026_results/logs/optical-analysis_20261124-162148.log` under the study directory.
