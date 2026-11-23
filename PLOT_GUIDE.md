# Run summaries and plots

For each new dataset, prepare a run-condition table and the optical, charge and comparison plots below. A dataset can contain several runs: make diagnostic images for each run, and streaming and physics plots across the runs.

## Run conditions

List the run ID, electrode voltages V0–V4, pressure, methane fraction and exposure time where known. Add

**V43+21 / P = (V4 − V3 + V2 − V1) / P**.

Use kV/bar for V43+21/P; its numerical value is the same as V/mbar. Mark unavailable or unverified conditions clearly, and flag any mismatch between a folder's run ID and its settings file.

## Optical (O)

- Per-run summary images: the integrated ToT image, x and y signal projections, and combined signal integral distribution, when produced by the optical analysis.
- Streaming plot: normalised optical signal S_O^norm against run, in acquisition order.
- Physics plot: S_O^norm against V43+21/P.
- Produce both linear-y and log-y streaming and physics plots when the data allow. Record the optical RMS and flag missing or unusually uncertain results.

## Charge (C = V50)

- Per-run V50 distributions from the channel-B pulse-height values. Choose each plot's x range to show the distribution and its peak; ranges do not have to match between runs. Keep the histogram binning clear and report event counts and values outside the displayed range.
- Streaming plot: V50 peak estimate against run, in acquisition order.
- Physics plot: V50 peak estimate against V43+21/P.
- Produce log-y streaming and physics plots, and linear-y versions where useful. Record the peak-finding method, estimated width, event counts and review flags. A missing or failed peak estimate is not evidence that no events were recorded.

## Comparisons

- **Charge overlay:** V50 physics plot comparing the relevant voltage scans and pressure passes.
- **Optical overlay:** S_O^norm physics plot comparing the relevant scans and passes.
- **Optical + paper overlay:** compare the optical results with the paper's reference plot. Identify any points outside the paper's fixed axes.
- **Optical/charge physics:** plot S_O^norm / V50 against V43+21/P using a linear y-axis. Compare the relevant scans and passes.
- Use hollow square markers for pressure runs and solid circles for voltage runs, with distinct colours and a legend for each pass or date. Identify exclusions and provisional points in an accompanying note or table.

## Error bars and review

For the ratio R = S_O^norm / V50, propagate the selected optical and V50 spreads assuming they are uncorrelated: σ_R = R × sqrt[(σ_O / O)^2 + (σ_V50 / V50)^2]. State what each spread represents. Optical RMS and a V50 width estimated from FWHM/2.355 are not automatically standard errors on the fitted peak; the resulting ratio bars are indicative spreads unless a validated uncertainty is available.

For linear plots, when requested, set the y maximum to 1.1 times the largest central value and indicate if error bars are clipped. Keep the underlying values and uncertainties available. Review low statistics, peak-finder fallback, high-end pile-up, missing results and large optical RMS before drawing conclusions.

## Output organisation

Keep the run-condition table, per-run optical images, V50 distributions, summary plots, comparison plots, numerical values and analysis notes together in the dataset's results directory. Label plots clearly with run IDs, axes, units and dataset names. Do not substitute charge p1 for V50 when making these requested C or O/C plots.
