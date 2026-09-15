#!/usr/bin/env python3
"""Generate Figure 6(e) from the authoritative failure workbook."""

from __future__ import annotations

import os
import re
from math import cos, radians, sin
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tables" / "failure.xlsx"
OUT_PATH = ROOT / "figures" / "generated" / "figure6_e_failure_distribution.pdf"

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT.parent / ".codex-cache" / "matplotlib"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

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
BASELINES = ["ours", "b1", "b2", "b3"]
BASELINE_LABELS = ["Ours", "End2End", "Agent per Robot", "COHERENT"]
BASELINE_COLORS = ["#2D5F8A", "#A66A3F", "#5A8F78", "#8270A6"]

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


def load_baseline_counts() -> dict[str, list[int]]:
    rows = read_rows(DATA_PATH)
    header_index = next(
        index for index, row in enumerate(rows)
        if row.get(1, "").strip().lower() == "baseline"
    )
    header = rows[header_index]
    columns = {
        name: column
        for column, name in header.items()
        if name in FAILURE_COLUMNS
    }
    counts = {}
    for row in rows[header_index + 1:]:
        method = row.get(1, "").strip().lower()
        if not method or method in {"ablation", "abaltion"}:
            break
        counts[method] = [
            int(float(row[columns[name]]))
            for name in FAILURE_COLUMNS
        ]
    if set(counts) != set(BASELINES):
        raise ValueError(f"Unexpected baseline keys: {sorted(counts)}")
    return counts


def counts_by_failure_type(counts: dict[str, list[int]]) -> list[list[int]]:
    return [
        [counts[baseline][failure_index] for baseline in BASELINES]
        for failure_index in range(len(FAILURE_COLUMNS))
    ]


def main() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman",
                       "DejaVu Serif"],
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    counts = load_baseline_counts()
    by_failure = counts_by_failure_type(counts)
    figure = plt.figure(figsize=(3.35, 1.45))
    axes = [
        figure.add_axes((0.015, 0.135, 0.225, 0.690)),
        figure.add_axes((0.260, 0.135, 0.225, 0.690)),
        figure.add_axes((0.505, 0.135, 0.225, 0.690)),
        figure.add_axes((0.750, 0.135, 0.225, 0.690)),
    ]
    handles = [
        Patch(facecolor=color, edgecolor="none", label=label)
        for color, label in zip(BASELINE_COLORS, BASELINE_LABELS)
    ]
    figure.legend(
        handles=handles,
        ncol=4,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.045),
        frameon=False,
        fontsize=8.0,
        handlelength=0.8,
        handleheight=0.9,
        columnspacing=0.70,
        handletextpad=0.35,
    )
    for axis, values, label in zip(axes, by_failure, FAILURE_LABELS):
        total = sum(values)
        wedges, texts = axis.pie(
            values,
            colors=BASELINE_COLORS,
            startangle=90,
            counterclock=False,
            wedgeprops={
                "width": 0.36,
                "linewidth": 0.58,
                "edgecolor": "white",
            },
        )
        for text in texts:
            text.set_visible(False)
        for value, wedge in zip(values, wedges):
            if value == 0:
                continue
            percentage = 100.0 * value / total
            angle = radians((wedge.theta1 + wedge.theta2) / 2.0)
            radius = 1.16
            x, y = radius * cos(angle), radius * sin(angle)
            axis.annotate(
                f"{percentage:.1f}%",
                xy=(0.99 * cos(angle), 0.99 * sin(angle)),
                xytext=(x, y),
                ha="left" if x >= 0 else "right",
                va="center",
                fontsize=5.3,
                color="#20252A",
                arrowprops={
                    "arrowstyle": "-",
                    "color": "#6B737A",
                    "linewidth": 0.35,
                    "shrinkA": 0,
                    "shrinkB": 0,
                },
            )
        axis.text(
            0.5,
            0.5,
            f"Total\n{total}",
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=8.0,
            fontweight="bold",
            color="#20252A",
            linespacing=0.88,
        )
        axis.text(
            0.5,
            -0.105,
            label,
            transform=axis.transAxes,
            ha="center",
            va="top",
            fontsize=8.0,
            fontweight="bold",
            color="#20252A",
            linespacing=0.90,
        )
        axis.set_aspect("equal")
        axis.axis("off")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUT_PATH, format="pdf", bbox_inches="tight", pad_inches=0.01)
    plt.close(figure)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
