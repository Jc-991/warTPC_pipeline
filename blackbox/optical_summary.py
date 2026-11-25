"""Write per-run optical summary tables from saved analysis results."""

import csv
import math
from pathlib import Path


CONDITION_COLUMNS = (
    "settings_id", "id_mismatch", "V0", "V1", "V2", "V3", "V4",
    "pressure_mbar", "methane_fraction", "exposure_time", "v_over_p", "unavailable",
)
TEXT_COLUMNS = (
    ("runID", "run"),
    ("settings_id", "settings_id"),
    ("id_mismatch", "id_mismatch"),
    *((f"V{index}_V", f"V{index}") for index in range(5)),
    ("pressure_mbar", "pressure_mbar"),
    ("methane_fraction", "methane_fraction"),
    ("exposure_time_ms", "exposure_time"),
    ("v_over_p_kVbar-1", "v_over_p"),
    ("unavailable", "unavailable"),
    ("original_exposure_ms", "exposure_before_s"),
    ("number_of_sparks", "spark_count"),
    ("number_of_sparkAlgo_iterations", "spark_algorithm_iterations"),
    ("total_spark_exposure_removed_ms", "exposure_excluded_s"),
    ("percentage_of_removed_exposure", "percentage_of_removed_exposure"),
    ("exposure_after_spark_removal_ms", "exposure_after_s"),
    ("S_O_ms", "S_O_ms"),
    ("S_O^norm_ms_per_s", "S_O_norm_ms_per_s"),
    ("S_O_error_in_percentage", "S_O_error_in_percentage"),
)
EXPOSURE_KEYS = {"exposure_time", "exposure_before_s", "exposure_excluded_s", "exposure_after_s"}


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def percentage(part, whole):
    return 100 * part / abs(whole) if part is not None and whole else None


def read_optical_values(run_dir, run):
    """Read the optical fit and the run conditions used by the plot table."""
    with (run_dir / "integral.csv").open(newline="") as handle:
        values = next(csv.reader(handle))
    signal, error = number(values[8]), number(values[9])
    original, excluded, usable = map(number, values[13:16])
    result = dict(
        exposure_before_s=original, exposure_after_s=usable, exposure_excluded_s=excluded,
        exposure_time=usable, S_O_norm_ms_per_s=signal, S_O_norm_rms_ms_per_s=error,
        S_O_ms=signal * usable if signal is not None and usable is not None else None,
        percentage_of_removed_exposure=percentage(excluded, original),
        S_O_error_in_percentage=percentage(error, signal),
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
    with path.open("w", newline="") as handle:
        handle.write("S_O^norm_ms_per_s = S_O_ms / (exposure_after_spark_removal_ms / 1000)\n")
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow([label for label, _ in TEXT_COLUMNS])
        values = []
        for _, key in TEXT_COLUMNS:
            value = row.get(key)
            if key in EXPOSURE_KEYS and value is not None:
                value *= 1000
            values.append(f"{value:.12g}" if isinstance(value, float) else value)
        writer.writerow(values)


def write_optical_summary(run_dir):
    run_dir = Path(run_dir)
    row = read_optical_values(run_dir, run_dir.name)
    status = dict(
        line.split(": ", 1)
        for line in (run_dir / "diagnostics" / "spark_status.txt").read_text().splitlines()
        if ": " in line
    )
    row.update(run=run_dir.name, spark_count=status["Spark count"],
               spark_algorithm_iterations=status["Spark algorithm iterations"])
    write_text_summary(run_dir / "run_summary.txt", row)
