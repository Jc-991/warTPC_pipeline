# Pipeline restructure and spark veto checkpoint

27 November 2026. Follows [2026-11-24-vr22-spark-study.md](2026-11-24-vr22-spark-study.md).

## How the pipeline runs now

Three steps, each run on Hammer from `/home/physics/phrvbh/warTPC/warTPC_pipeline`
inside a compute allocation, after `source blackbox/setup_blackbox.sh`.

1. **Decode once per dataset, straight from the uploaded ZIP.**
   `scripts/stages/decode.sh -i <zip or unzipped folder> -o ~/warTPC/decoded_data`.
   A bare ZIP name is looked up in `/storage/phsccs_grp/transfer/`. The ZIP is
   unzipped into a temporary folder, `tpx3dump` runs once per run, and the
   temporary copy is deleted. Only `output.hdf5` and `settings.csv` are kept, in
   `decoded_data/<zip name>/optical/<run>/`. These are the only per-run files the
   optical fits and plots read. Charge has no decode step and is not stored.
2. **Analyse with `scripts/workflow.sh -i ~/warTPC/decoded_data/<dataset> -o <output_dir>`.**
   It never decodes and is optical only. It runs the uncut fit (`before/`), the
   cut fit, both plot sets, then the before/after pairs into
   `<dataset>_results/plots/optical_per_run/`.
3. **Compare datasets separately with `scripts/compare-optical-results.sh`.**
   Pass `-i <dataset>_results/plots` once per dataset and `-o` a new folder.
   `workflow.sh` makes no comparison plots: `stages/plot.sh` always passes
   `--no-comparisons`.

Decoding all uploaded voltage runs:

```bash
for z in /storage/phsccs_grp/transfer/voltage-run-*.zip; do bash scripts/stages/decode.sh -i "$z" -o /home/physics/phrvbh/warTPC/decoded_data; done 2>&1 | tee /home/physics/phrvbh/warTPC/decoded_data/decode-voltage.log
```

## Stage scripts (`scripts/stages/`)

| Script | Does | Key options |
|---|---|---|
| `decode.sh` | ZIP or raw folder → `decoded_data/<dataset>/optical/<run>/` | `--runs`, `--force`, `--timeout MIN` (default 10, 0 = none), `--tmp DIR` |
| `fit.sh` | Spark cut and `optical-analysis.py` on the decoded HDF5 | `-r <results>`, `-d <decoded dataset>` (required), `--spark off\|remove`, `--veto B,A`, `--runs`, `--rebin-x`, `--analysis FILE` |
| `plot.sh` | `build/plot` on one fit folder | `--from before`, `--organise` (only when `pair.sh` will not run) |
| `pair.sh` | Before/after pairs into `plots/optical_per_run/`, then plot IDs | `--runs` |

- `workflow.sh` options are `--runs`, `--kind`, `--sparks on|off`,
  `--veto B,A|off` (default `1,20`) and `--rebin-x`. Removed today: `--raw`,
  `--run charge|both`, `--no-plot`, `--decoded` and `--decode-timeout`.
  `--run optical` and `--plot` are still accepted for older commands.
- `fit.sh` clears a run's folder before fitting, so a failed fit cannot leave an
  old `integral.csv`. `optical_status.txt` names runs that were never decoded.
- Results folders hold no HDF5 and no `decoded` link. `workflow.sh` deletes
  `before/` and `paired/` after the pair step, leaving `optical/`, `logs/` and `plots/`.
- A rerun of selected runs into an existing `<dataset>_results` goes to
  `<dataset>_results-01`, `-02`, … (no more random suffixes).
  `run-vr22-spark-study.sh` writes `vr22-spark-study-01`, `-02`, ….
- Charge runs on its own: `build/charge -i <raw dataset> -o <dataset>_results`,
  then `plot.sh` and `pair.sh` again.

## Decode reporting

- A run whose `tpx3dump` exceeds the time limit is stopped, along with any
  child processes, and marked failed. The next run starts. Its partial HDF5 is deleted.
- Per dataset: `decoded_data/<dataset>/decode_status.txt` (last pass) and
  `logs/decode/<run>.log`.
- All datasets: `decoded_data/decode_report.tsv` is appended with time, dataset,
  run, `OK`/`TIMEOUT`/`FAILED`, seconds and reason. Find timeouts with `grep TIMEOUT`.
- The 10-minute default is untested against real decode times. Check the
  `OK (… s)` times on the first real pass.

## Spark veto (−1 s, +20 s)

- `blackbox/spark_detection.py` widens each flagged 5 ms window to
  [start − before, end + after). It merges overlaps and removes every hit inside.
  Exposure loses the union of the vetoes inside the run.
  Set by `WARTPC_SPARK_VETO_BEFORE_S` / `_AFTER_S`. Both default to 0, giving the old cut.
  `spark_status.txt` lists `Veto since first hit (s)` intervals.
- `workflow.sh` applies `--veto 1,20` by default. `fit.sh` needs `--veto` explicitly.
- `report-vr22-sparks.py` now writes veto intervals to `excluded_intervals.csv`.
- `scripts/test-spark-veto.py` compares the standard cut with a veto on HDF5
  files, without fitting. `--self-test` runs synthetic checks.

### vr22-07 veto test (Hammer, `~/warTPC/results/veto-test-01`, copied to `~/Desktop/veto-test-01`)

| Quantity | Standard 5 ms cut | −1 s / +20 s veto |
|---|---:|---:|
| Hits (of 499,119) kept | 267,654 | 152,841 |
| Exposure excluded | 0.025 s | 42.23 s (22.2% of 189.988 s) |
| Merged intervals | 5 windows | 25.44–46.67 s and 95.47–116.48 s |

- The 5 flagged windows split as **4 between 26.44 and 26.67 s** and **1 at 96.47 s**.
  This resolves the split left open in the earlier checkpoint.
- The veto removes about 114,800 extra hits over about 42 s, roughly 2,700 hits/s.
  The kept hits average about 1,030 hits/s. Activity therefore stays about 2.7× higher
  in the 20 s after a spark than elsewhere in this run. This is one run; check all VR22 runs.
- The input HDF5 was `~/warTPC/results/full-vr22-optical-2/voltage-run-22-11-2026_results/optical/vr22-07/output.hdf5`.
  The raw data folders hold no HDF5.

## ToT-versus-arrival-time image

- Time columns are now **5 ms**, aligned with the spark grouping. They were 10 ms before today
  and for the run 7 slides.
- A full run has about 38,000 columns at 5 ms against about 1,700 image pixels.
  Nearest-pixel drawing could drop a single 5 ms spark, so each pixel now shows
  the largest bin it covers. The colour bar states the group size.
- The statistics box in the top-left covers the first ~30 s at high ToT. The top
  of run 7's 26 s spark column sits behind it. Not yet moved.

## Open items

- Real Hammer runs of the new stages have not been checked against earlier vr22-07
  output. Unchecked: the `tpx3dump` call, ROOT fits, module loading and the 10-minute limit.
- `decoded_data` naming follows the ZIP: VR22 decodes as `voltage-run-22-11-2026`.
  This differs from the renamed `voltage-run-22-11-26` raw folder.
  Existing VR22 HDF5 from `full-vr22-optical-2` can be copied into `decoded_data` to skip decoding.
- `optical-analysis.sh` and `run-vr22-spark-study.sh` still use the old decode-every-time route.
- `decode.sh` header comment was shortened locally (uncommitted). Its `usage()` prints
  lines 2–33 of the file, so `-h` now shows code. Adjust the line range or restore the comment.
- Pressure passes are decoded the same way with `pressure-pass-*.zip`.
