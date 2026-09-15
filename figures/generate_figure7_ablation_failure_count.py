#!/usr/bin/env python3
"""Generate the ablation matrix (Figure 8 in the manuscript) from failure.xlsx."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tables" / "failure.xlsx"
OUT_PATH = ROOT / "figures" / "generated" / "figure7_ablation_failure_count.pdf"

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT.parent / ".codex-cache" / "matplotlib"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

FAILURE_COLUMNS = [
    "invalid_capability_count",
    "execution_anomaly_count",
    "assignment_conflict_count",
    "task_timeout_count",
]
FAILURE_LABELS = [
    "Invalid\ncapability",
    "Execution\nanomaly",
    "Assignment\nconflict",
    "Task\ntimeout",
]
FAILURE_COLORS = ["#4C78A8", "#72B7B2", "#E0A458", "#B279A2"]
METHOD_LABELS = {
    "ours": "Ours",
    "a1": "A1",
    "a2": "A2",
}
METHOD_ORDER = ["ours", "a1", "a2"]


def col_index(cell_ref: str) -> int:
    match = re.match(r"[A-Z]+", cell_ref)
    if match is None:
        raise ValueError(f"Invalid cell reference: {cell_ref}")
    index = 0
    for char in match.group(0):
        index = index * 26 + ord(char) - ord("A") + 1
    return index


def read_rows(path: Path) -> list[dict[int, str]]:
    with ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(NS + "si"):
                shared.append("".join(t.text or "" for t in item.iter(NS + "t")))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(PKG_NS + "Relationship")
        }
        sheet = workbook.find(NS + "sheets").find(NS + "sheet")
        target = relmap[sheet.attrib[REL_NS + "id"]].lstrip("/")
        sheet_path = target if target.startswith("xl/") else f"xl/{target}"
        worksheet = ET.fromstring(archive.read(sheet_path))

        rows = []
        for row in worksheet.findall(NS + "sheetData/" + NS + "row"):
            values = {}
            for cell in row.findall(NS + "c"):
                value = cell.find(NS + "v")
                if value is None:
                    continue
                raw = value.text or ""
                if cell.attrib.get("t") == "s":
                    raw = shared[int(raw)]
                values[col_index(cell.attrib["r"])] = raw
            if values:
                rows.append(values)
        return rows


def load_ablation_counts() -> dict[str, list[int]]:
    rows = read_rows(DATA_PATH)
    header = next(row for row in rows if row.get(1, "").strip() == "Baseline")
    columns = {
        name: column
        for column, name in header.items()
        if name in FAILURE_COLUMNS
    }
    start = next(
        index for index, row in enumerate(rows)
        if row.get(1, "").strip().lower() in {"ablation", "abaltion"}
    )
    counts = {}
    for row in rows[start + 1:]:
        method = row.get(1, "").strip().lower()
        if not method:
            break
        counts[method] = [
            int(float(row[columns[name]]))
            for name in FAILURE_COLUMNS
        ]
    if set(counts) != set(METHOD_ORDER):
        raise ValueError(f"Unexpected ablation methods: {sorted(counts)}")
    return counts


def draw_matrix_bar_chart(counts: dict[str, list[int]]) -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman",
                       "DejaVu Serif"],
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    figure, axis = plt.subplots(figsize=(3.42, 0.98))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")

    left = 0.105
    right = 0.995
    top = 0.700
    bottom = 0.070
    cols = len(FAILURE_COLUMNS)
    rows = len(METHOD_ORDER)
    cell_w = (right - left) / cols
    cell_h = (top - bottom) / rows
    max_count = max(max(values) for values in counts.values())

    for col, (label, color) in enumerate(zip(FAILURE_LABELS, FAILURE_COLORS)):
        cx = left + (col + 0.5) * cell_w
        axis.text(
            cx,
            0.865,
            label,
            ha="center",
            va="center",
            fontsize=7.2,
            fontweight="bold",
            color="#20252A",
        )
        axis.add_patch(Rectangle(
            (left + col * cell_w, top + 0.010),
            cell_w,
            0.012,
            facecolor=color,
            edgecolor="none",
            alpha=0.95,
        ))

    for row, method in enumerate(METHOD_ORDER):
        y0 = top - (row + 1) * cell_h
        cy = y0 + 0.5 * cell_h
        axis.text(
            0.012,
            cy,
            METHOD_LABELS[method],
            ha="left",
            va="center",
            fontsize=7.8,
            fontweight="bold" if method == "ours" else "normal",
            color="#20252A",
        )
        for col, color in enumerate(FAILURE_COLORS):
            x0 = left + col * cell_w
            value = counts[method][col]
            axis.add_patch(Rectangle(
                (x0 + 0.005, y0 + 0.012),
                cell_w - 0.010,
                cell_h - 0.024,
                facecolor="#FBFCFD",
                edgecolor="#D6DCE2",
                linewidth=0.35,
            ))
            bar_max = cell_w - 0.052
            bar_w = max(bar_max * value / max_count, bar_max * 0.030)
            bar_h = cell_h * 0.250
            bar_x = x0 + 0.018
            bar_y = cy - bar_h / 2
            axis.add_patch(Rectangle(
                (bar_x, bar_y),
                bar_w,
                bar_h,
                facecolor=color,
                edgecolor="none",
                alpha=0.94 if value else 0.60,
            ))
            label_x = min(bar_x + bar_w + 0.010, x0 + cell_w - 0.015)
            axis.text(
                label_x,
                cy,
                str(value),
                ha="left",
                va="center",
                fontsize=7.6,
                color="#20252A",
            )

    axis.plot([left, right], [top + 0.024, top + 0.024],
              color="#20252A", linewidth=0.45)
    axis.plot([left, right], [bottom, bottom], color="#20252A", linewidth=0.45)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUT_PATH, bbox_inches="tight", pad_inches=0.012)
    plt.close(figure)


def main() -> None:
    counts = load_ablation_counts()
    draw_matrix_bar_chart(counts)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
