"""Lectura y escritura CSV del contrato bronze."""

from __future__ import annotations

import csv
from pathlib import Path

from contract import TABLE_ORDER, columns


def csv_path(raw_dir: Path, table: str) -> Path:
    return raw_dir / f"{table}.csv"


def write_table(path: Path, table: str, rows: list[dict[str, str]]) -> None:
    cols = columns(table)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=cols,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in cols})


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            return next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV vacío (sin header): {path}") from exc


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV vacío (sin header): {path}")
        return list(reader)


def count_data_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV vacío (sin header): {path}") from exc
        return sum(1 for _ in reader)


def expected_headers() -> dict[str, list[str]]:
    return {table: columns(table) for table in TABLE_ORDER}
