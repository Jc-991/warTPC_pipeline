"""Write per-run optical summary tables from saved analysis results."""

import csv
import math
from statistics import fmean
from pathlib import Path


CONDITION_COLUMNS = (
    "settings_id", "id_mismatch", "V0", "V1", "V2", "V3", "V4",
    "pressure_mbar", "methane_fraction", "exposure_time", "v_over_p", "unavailable",
)
VARIATION_FILE = "projection_variations.csv"
VARIATION_COLUMNS = ("axis", "polynomial_degree", "signal_sigma", "sideband_sigma",
                     "mean_pixel", "rms_pixel", "background_norm_ms_per_s", "signal_ms", "background_ms")
PROJECTION_COLUMNS = ("X_mean", "X_RMS", "Y_mean", "Y_RMS", "B_X_norm", "B_Y_norm", "A", "A_X", "A_Y", "B_X", "B_Y")
VARIATION_SUMMARY_COLUMNS = ("S_O_X_ms", "S_O_Y_ms", "B_O_ms")
TEXT_COLUMNS = (
    ("runID", "run"),
    ("settings_id", "settings_id"),
    ("id_mismatch", "id_mismatch"),
    ("unavailable", "unavailable"),
    *((f"V{index}_V", f"V{index}") for index in range(5)),
    ("pressure_mbar", "pressure_mbar"),
    ("methane_fraction", "methane_fraction"),
    ("v_over_p_kVbar-1", "v_over_p"),
    ("original_exposure_s", "exposure_before_s"),
    ("exposure_time_s", "exposure_time"),
    ("number_of_sparks", "spark_count"),
    ("number_of_sparkAlgo_iterations", "spark_algorithm_iterations"),
    ("total_spark_exposure_removed_s", "exposure_excluded_s"),
    ("fraction_of_removed_exposure", "fraction_of_removed_exposure"),
    ("exposure_after_spark_removal_s", "exposure_after_s"),
    *((key, key) for key in ("A", "A_X", "A_Y")),
    ("S_O_ms", "S_O_ms"),
    ("S_O^norm_ms_per_s", "S_O_norm_ms_per_s"),
    ("S_O_error_fraction", "S_O_error_fraction"),
    *((key, key) for key in ("S_O_X_ms", "S_O_Y_ms")),
    ("B_O_ms", "B_O_ms"),
    *((key, key) for key in ("B_X", "B_Y", "B_X_norm", "B_Y_norm")),
    *((key, key) for key in ("X_mean", "X_RMS", "Y_mean", "Y_RMS")),
)


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def absolute_fraction(part, whole):
    return abs(part / whole) if part is not None and whole else None


def read_optical_values(run_dir, run):
    """Read the optical fit and the run conditions used by the plot table."""
    with (run_dir / "integral.csv").open(newline="") as handle:
        values = next(csv.reader(handle))
    signal, error = number(values[8]), number(values[9])
    original, excluded, usable = map(number, values[13:16])
    removed_fraction = absolute_fraction(excluded, original)
    error_fraction = absolute_fraction(error, signal)
    result = dict(
        exposure_before_s=original, exposure_after_s=usable, exposure_excluded_s=excluded,
        exposure_time=usable, S_O_norm_ms_per_s=signal, S_O_norm_rms_ms_per_s=error,
        S_O_ms=signal * usable if signal is not None and usable is not None else None,
        fraction_of_removed_exposure=removed_fraction,
        S_O_error_fraction=error_fraction,
        percentage_of_removed_exposure=None if removed_fraction is None else 100 * removed_fraction,
        S_O_error_in_percentage=None if error_fraction is None else 100 * error_fraction,
    )
    try:
        with (run_dir / "settings.csv").open(newline="") as handle:
            settings = next(csv.reader(handle))
    except (OSError, StopIteration):
        settings = values
    settings = (settings + [""] * 8)[:8]
    result["settings_id"] = settings[0].strip()
    result["id_mismatch"] = int(result["settings_id"] != run)
    pressure = result["pressure_mbar"] = number(settings[1])
    voltage = [number(value) for value in settings[2:7]]
    result.update(zip(("V0", "V1", "V2", "V3", "V4"), voltage))
    result["methane_fraction"] = number(settings[7])
    if pressure and pressure > 0 and None not in voltage:
        result["v_over_p"] = (voltage[4] - voltage[3] + voltage[2] - voltage[1]) / pressure
    result["unavailable"] = int(
        not result["settings_id"] or any(
            result.get(key) is None for key in CONDITION_COLUMNS[2:-1]
        )
    )
    return result


def projection_label(key, position_unit):
    if key in ("X_mean", "X_RMS", "Y_mean", "Y_RMS"):
        unit = "pixel" if position_unit == "pixel" else "ms"
    else:
        unit = "ms_per_s" if key.endswith("_norm") else "ms"
    if key.startswith(("A", "B")):
        family, _, suffix = key.partition("_")
        key = "_".join(part for part in (family, "O", suffix) if part)
    return f"{key}_{unit}"


def write_text_summary(path, row):
    unit = row.get("projection_position_unit")
    labels = [projection_label(key, unit) if key in PROJECTION_COLUMNS else label
              for label, key in TEXT_COLUMNS]
    values = []
    for _, key in TEXT_COLUMNS:
        value = row.get(key)
        values.append(f"{value:.12g}" if isinstance(value, float) else value)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(labels)
        writer.writerow(values)

    width = max(map(len, labels))
    readable = path.with_name(f"{path.stem}_readable{path.suffix}")
    with readable.open("w") as handle:
        handle.write("S_O^norm_ms_per_s = S_O_ms / exposure_after_spark_removal_s\n")
        if row.get("projection_position_unit") == "pixel":
            handle.write("X/Y mean and RMS are in pixels, weighted by positive residual ToT.\n")
        else:
            handle.write("X/Y mean and RMS use residual ToT (ms).\n")
        handle.write("B_O_X_norm_ms_per_s and B_O_Y_norm_ms_per_s are exposure-normalized.\n")
        handle.write("A_O_ms = A_O_X_ms = A_O_Y_ms.\n")
        handle.write("S_O_X_ms, S_O_Y_ms and B_O_ms are means across fit settings.\n")
        handle.write("Absolute fractions: 1 = 100%.\n\n")
        for label, value in zip(labels, values):
            if value is None or value == "":
                value = "N/A"
            handle.write(f"{label:<{width}}  {value}\n")


def read_projection_observables(path):
    try:
        with path.open(newline="") as handle:
            row = next(csv.DictReader(handle, delimiter="\t"))
    except (FileNotFoundError, StopIteration):
        return {}
    unit = "pixel" if "X_mean_pixel" in row else row.get("projection_position_unit")
    result = {}
    for key in PROJECTION_COLUMNS:
        label = projection_label(key, unit)
        old_label = label.replace("A_O_", "A_", 1).replace("B_O_", "B_", 1)
        result[key] = number(row.get(label, row.get(old_label, row.get(key))))
    for key in VARIATION_SUMMARY_COLUMNS:
        result[key] = fit_mean((row.get(key) or "").split(","))
    for axis in ("X", "Y"):
        if result[f"A_{axis}"] is None:
            result[f"A_{axis}"] = result["A"]
    result["projection_position_unit"] = unit
    exposure = number(row.get("exposure_after_spark_removal_s"))
    if exposure is not None and exposure > 0:
        for key in ("B_X", "B_Y"):
            normalized = result[f"{key}_norm"]
            if result[key] is None and normalized is not None:
                result[key] = normalized * exposure
    return result


def projection_variation(axis, degree, signal_sigma, sideband_sigma, positions, residuals,
                         background_norm, signal_ms, background_ms):
    """Use positive, background-subtracted ToT as the position weights."""
    weights = [max(0.0, float(value)) for value in residuals]
    total = math.fsum(weights)
    mean = rms = None
    if total > 0 and math.isfinite(total):
        mean = math.fsum(x * weight for x, weight in zip(positions, weights)) / total
        rms = math.sqrt(math.fsum(
            weight * (x - mean) ** 2 for x, weight in zip(positions, weights)
        ) / total)
    return dict(axis=axis, polynomial_degree=degree, signal_sigma=signal_sigma,
                sideband_sigma=sideband_sigma, mean_pixel=mean, rms_pixel=rms,
                background_norm_ms_per_s=background_norm, signal_ms=signal_ms,
                background_ms=background_ms)


def fit_mean(values):
    finite = [value for item in values if (value := number(item)) is not None]
    return fmean(finite) if finite else None


def variation_summary(variations):
    return {
        "S_O_X_ms": fit_mean(fit["signal_ms"] for fit in variations if fit["axis"] == "X"),
        "S_O_Y_ms": fit_mean(fit["signal_ms"] for fit in variations if fit["axis"] == "Y"),
        "B_O_ms": fit_mean(fit["background_ms"] for fit in variations),
    }

def write_optical_summary(run_dir, projection_observables, variations):
    with (Path(run_dir) / "diagnostics" / VARIATION_FILE).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=VARIATION_COLUMNS)
        writer.writeheader()
        writer.writerows(variations)
    run_dir = Path(run_dir)
    row = read_optical_values(run_dir, run_dir.name)
    status = dict(
        line.split(": ", 1)
        for line in (run_dir / "diagnostics" / "spark_status.txt").read_text().splitlines()
        if ": " in line
    )
    row.update(run=run_dir.name, spark_count=status["Spark count"],
               spark_algorithm_iterations=status["Spark algorithm iterations"])
    row.update(projection_observables, projection_position_unit="pixel")
    row.update(A_X=row.get("A"), A_Y=row.get("A"))
    row.update(variation_summary(variations))
    write_text_summary(run_dir / "run_summary.txt", row)
