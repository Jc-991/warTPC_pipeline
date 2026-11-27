"""Combine exported per-run TSV summaries into a dataset table."""

import csv
import re


def write_combined_run_summary(plots_dir):
    per_run = plots_dir / "optical_per_run"
    paths = sorted(per_run.glob("*/run_summary.txt"), key=lambda path: [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", path.parent.name)
    ])
    fields, rows = [], []
    for path in paths:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            fields.extend(field for field in (reader.fieldnames or ()) if field not in fields)
            rows.extend(reader)

    output = plots_dir / "run_summary.txt"
    if not rows:
        output.unlink(missing_ok=True)
        return

    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
