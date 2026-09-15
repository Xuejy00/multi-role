#!/usr/bin/env python3
"""Generate Figure 5 subplots from tables/baseline.xlsx."""

from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parents[2] / ".codex-cache" / "matplotlib"),
)

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tables" / "baseline.xlsx"
OUT_DIR = ROOT / "figures" / "generated"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

CONDITIONS = ["C1", "C2-E1", "C2-E2", "C2-E3", "C3", "C4-E1", "C4-E2", "C4-E3"]
METHOD_LABELS = {
    "Ours": "Ours",
    "B1": "End2End",
    "B2": "Agent per Robot",
    "B3": "COHERENT",
}
BAR_LABELS = {
    "Ours": "Ours",
    "B1": "End2End",
    "B2": "Agent\nper Robot",
    "B3": "COHERENT",
}
COLORS = {
    "Ours": "#2D5F8A",
    "B1": "#A66A3F",
    "B2": "#5A8F78",
    "B3": "#8270A6",
}
MARKERS = {
    "Ours": "o",
    "B1": "s",
    "B2": "^",
    "B3": "D",
}
LINESTYLES = {
    "Ours": "-",
    "B1": "--",
    "B2": ":",
    "B3": "-.",
}


def col_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    idx = 0
    for char in letters:
        idx = idx * 26 + ord(char) - ord("A") + 1
    return idx


def workbook_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"


def cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(NS + "t"))

    value = cell.find(NS + "v")
    if value is None:
        return ""
    raw = value.text or ""
    if cell_type == "s":
        return shared[int(raw)]
    return raw


def read_first_sheet(path: Path) -> list[list[str]]:
    with ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for string_item in root.findall(NS + "si"):
                shared.append("".join(t.text or "" for t in string_item.iter(NS + "t")))

        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relmap = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(PKG_NS + "Relationship")
        }
        first_sheet = workbook.find(NS + "sheets").find(NS + "sheet")
        sheet_path = workbook_target(relmap[first_sheet.attrib[REL_NS + "id"]])
        worksheet = ET.fromstring(zf.read(sheet_path))

        rows = []
        for row in worksheet.findall(NS + "sheetData/" + NS + "row"):
            values = {
                col_index(cell.attrib["r"]): cell_value(cell, shared)
                for cell in row.findall(NS + "c")
            }
            max_col = max(values, default=0)
            rows.append([values.get(i, "") for i in range(1, max_col + 1)])
        return rows


def parse_percent(raw: str) -> float:
    return float(raw.strip().removesuffix("%"))


def parse_metric_cell(raw: str) -> dict[str, float]:
    pattern = (
        r"^\s*([0-9.]+)%\s*/\s*([0-9.]+)%\s*/\s*([0-9.]+)"
        r"\s*/\s*(N/A|[0-9.]+)\s*/\s*([0-9.]+)k\s*$"
    )
    match = re.match(pattern, raw)
    if match is None:
        raise ValueError(f"Unexpected metric cell: {raw}")
    tsr, scr, reasoning, makespan_raw, token = match.groups()
    makespan = math.nan if makespan_raw == "N/A" else float(makespan_raw)
    return {
        "tsr": float(tsr),
        "scr": float(scr),
        "reasoning": float(reasoning) * 100.0,
        "makespan": makespan,
        "token": float(token),
    }


def load_metrics() -> dict[str, dict[str, list[float]]]:
    rows = read_first_sheet(DATA_PATH)
    metrics = {}
    for row in rows[2:6]:
        method = row[0]
        cells = row[2:10]
        metrics[method] = {
            "scr": [],
            "reasoning": [],
            "token": [],
            "makespan": [],
        }
        for cell in cells:
            parsed = parse_metric_cell(cell)
            for key in metrics[method]:
                metrics[method][key].append(parsed[key])
    return metrics


def configure_matplotlib() -> None:
    plt.rcParams.update({
        "backend": "pdf",
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.linewidth": 0.45,
        "axes.labelsize": 8.0,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0,
        "legend.fontsize": 8.0,
    })


def plot_metric(
    metrics: dict[str, dict[str, list[float]]],
    key: str,
    ylabel: str,
    out_name: str,
    ylim: tuple[float, float],
    yticks: list[float],
    ylabel_size: float | None = None,
    ylabel_y: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(1.67, 1.18))
    x = list(range(len(CONDITIONS)))
    for method in ["Ours", "B1", "B2", "B3"]:
        ax.plot(
            x,
            metrics[method][key],
            color=COLORS[method],
            marker=MARKERS[method],
            linestyle=LINESTYLES[method],
            linewidth=0.95,
            markersize=2.6,
            markerfacecolor="white" if method != "Ours" else COLORS[method],
            markeredgewidth=0.65,
            label=METHOD_LABELS[method],
        )

    ax.set_ylabel(ylabel, labelpad=1.2)
    if ylabel_size is not None:
        ax.yaxis.label.set_size(ylabel_size)
    if ylabel_y is not None:
        ax.yaxis.set_label_coords(-0.18, ylabel_y)
    ax.set_xticks(x)
    ax.set_xticklabels(
        [
            "C1",
            "C2\nE1",
            "C2\nE2",
            "C2\nE3",
            "C3",
            "C4\nE1",
            "C4\nE2",
            "C4\nE3",
        ],
        rotation=0,
        fontstyle="normal",
        linespacing=0.9,
    )
    ax.set_ylim(*ylim)
    ax.set_yticks(yticks)
    ax.grid(axis="y", color="#D6DCE2", linewidth=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", width=0.45, length=2.0, pad=1.2)

    fig.savefig(OUT_DIR / out_name, bbox_inches="tight", pad_inches=0.012)
    plt.close(fig)


def finite_mean(values: list[float]) -> float:
    finite = [value for value in values if not math.isnan(value)]
    if not finite:
        return math.nan
    return sum(finite) / len(finite)


def plot_average_bar(
    metrics: dict[str, dict[str, list[float]]],
    key: str,
    ylabel: str,
    out_name: str,
    ylim: tuple[float, float],
    yticks: list[float],
    auto_headroom: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(2.05, 1.18))
    methods = ["Ours", "B1", "B2", "B3"]
    x = list(range(len(methods)))
    means = [finite_mean(metrics[method][key]) for method in methods]
    if auto_headroom:
        finite_means = [mean for mean in means if not math.isnan(mean)]
        if finite_means:
            ylim = (ylim[0], max(ylim[1], max(finite_means) * 1.12))
    label_padding = (ylim[1] - ylim[0]) * 0.018
    bars = ax.bar(
        x,
        means,
        width=0.56,
        color=[COLORS[method] for method in methods],
        edgecolor="#20252A",
        linewidth=0.45,
    )

    for bar, mean in zip(bars, means):
        if math.isnan(mean):
            continue
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            mean + label_padding,
            f"{mean:.1f}",
            ha="center",
            va="bottom",
            fontsize=8.0,
        )

    ax.set_ylabel(ylabel, labelpad=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels([BAR_LABELS[method] for method in methods])
    ax.set_ylim(*ylim)
    ax.set_yticks(yticks)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", width=0.45, length=2.0, pad=1.2)
    ax.tick_params(axis="x", labelsize=8.0)
    fig.savefig(OUT_DIR / out_name, bbox_inches="tight", pad_inches=0.012)
    plt.close(fig)


def main() -> None:
    configure_matplotlib()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = load_metrics()
    plot_metric(
        metrics,
        "scr",
        "SCR (%)",
        "figure5_a_scr.pdf",
        (0, 105),
        [0, 25, 50, 75, 100],
    )
    plot_metric(
        metrics,
        "reasoning",
        "Reasoning Time Ratio (%)",
        "figure5_b_reasoning_time.pdf",
        (0, 105),
        [0, 25, 50, 75, 100],
        ylabel_size=6.6,
        ylabel_y=0.45,
    )
    plot_average_bar(
        metrics,
        "token",
        r"Token Usage ($\times10^3$)",
        "figure5_c_token_usage.pdf",
        (0, 165),
        [0, 50, 100, 150, 200],
        auto_headroom=True,
    )
    plot_average_bar(
        metrics,
        "makespan",
        "Makespan (s)",
        "figure5_d_makespan.pdf",
        (0, 36),
        [0, 10, 20, 30],
    )


if __name__ == "__main__":
    main()
