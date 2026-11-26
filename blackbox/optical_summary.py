"""Write per-run optical summary tables from saved analysis results."""

import csv
import math
from pathlib import Path


CONDITION_COLUMNS = (
    "settings_id", "id_mismatch", "V0", "V1", "V2", "V3", "V4",
    "pressure_mbar", "methane_fraction", "exposure_time", "v_over_p", "unavailable",
)
VARIATION_FILE = "projection_variations.csv"
VARIATION_COLUMNS = ("axis", "polynomial_degree", "signal_sigma", "sideband_sigma",
                     "mean_pixel", "rms_pixel", "background_norm_ms_per_s")
PROJECTION_COLUMNS = ("X_mean", "X_RMS", "Y_mean", "Y_RMS", "B_X_norm", "B_Y_norm", "A", "A_X", "A_Y", "B_X", "B_Y")
TEXT_COLUMNS = (
    ("runID", "run"),
    ("settings_id", "settings_id"),
    ("id_mismatch", "id_mismatch"),
    *((f"V{index}_V", f"V{index}") for index in range(5)),
    ("pressure_mbar", "pressure_mbar"),
    ("methane_fraction", "methane_fraction"),
    ("exposure_time_s", "exposure_time"),
    ("v_over_p_kVbar-1", "v_over_p"),
    ("unavailable", "unavailable"),
    ("original_exposure_s", "exposure_before_s"),
    ("number_of_sparks", "spark_count"),
    ("number_of_sparkAlgo_iterations", "spark_algorithm_iterations"),
    ("total_spark_exposure_removed_s", "exposure_excluded_s"),
    ("fraction_of_removed_exposure", "fraction_of_removed_exposure"),
    ("exposure_after_spark_removal_s", "exposure_after_s"),
    ("S_O_ms", "S_O_ms"),
    ("S_O^norm_ms_per_s", "S_O_norm_ms_per_s"),
    ("S_O_error_fraction", "S_O_error_fraction"),
    *((key, key) for key in PROJECTION_COLUMNS),
    ("projection_position_unit", "projection_position_unit"),
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


def write_text_summary(path, row):
    labels = [label for label, _ in TEXT_COLUMNS]
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
        handle.write("B_X_norm and B_Y_norm use ms/s.\n")
        handle.write("A = A_X = A_Y. A and B_X/B_Y are summed ToT (ms).\n")
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
    result = {key: number(row.get(key)) for key in PROJECTION_COLUMNS}
    for axis in ("X", "Y"):
        if result[f"A_{axis}"] is None:
            result[f"A_{axis}"] = result["A"]
    result["projection_position_unit"] = row.get("projection_position_unit")
    exposure = number(row.get("exposure_after_spark_removal_s"))
    if exposure is not None and exposure > 0:
        for key in ("B_X", "B_Y"):
            normalized = result[f"{key}_norm"]
            if result[key] is None and normalized is not None:
                result[key] = normalized * exposure
    return result


def projection_variation(axis, degree, signal_sigma, sideband_sigma, positions, residuals,
                         background_norm):
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
                background_norm_ms_per_s=background_norm)


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
    write_text_summary(run_dir / "run_summary.txt", row)
