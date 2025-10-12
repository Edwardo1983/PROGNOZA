"""QA report builders for Janitza CSV validation."""
from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path
from typing import Dict, Optional

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _figure_to_data_uri(fig: plt.Figure) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _histogram_image(stats: Dict[str, object]) -> str:
    hist = stats.get("alignment_histogram") or {}
    bins = hist.get("bins") or []
    counts = hist.get("counts") or []
    if not bins or not counts:
        return ""

    bins = np.asarray(bins)
    counts = np.asarray(counts)
    widths = np.diff(bins)

    fig, ax = plt.subplots(figsize=(4, 1.2))
    ax.bar(bins[:-1], counts, width=widths, align="edge", color="#2b6cb0")
    ax.set_title("Drift Histogram (s)", fontsize=8)
    ax.tick_params(axis="both", labelsize=6)
    ax.set_ylabel("count", fontsize=7)
    ax.set_xlabel("seconds", fontsize=7)
    fig.tight_layout()
    return _figure_to_data_uri(fig)


def _missing_map_image(stats: Dict[str, object]) -> str:
    missing_map = stats.get("missing_map") or {}
    timestamps = missing_map.get("timestamps") or []
    present = missing_map.get("present") or []
    if not timestamps:
        return ""

    values = np.asarray(present, dtype=float).reshape(1, -1)
    fig, ax = plt.subplots(figsize=(6, 1.2))
    img = ax.imshow(values, aspect="auto", cmap="Greens", interpolation="nearest", vmin=0, vmax=1)
    ax.set_title("Minute Coverage", fontsize=8)
    ax.set_yticks([])
    ax.set_xticks([0, len(timestamps) - 1])
    ax.set_xticklabels([timestamps[0][:16], timestamps[-1][:16]], rotation=0, fontsize=6)
    fig.colorbar(img, ax=ax, orientation="horizontal", fraction=0.2, pad=0.15)
    fig.tight_layout()
    return _figure_to_data_uri(fig)


def _range_bar_image(stats: Dict[str, object]) -> str:
    ranges = stats.get("value_ranges") or {}
    if not ranges:
        return ""
    labels = list(ranges.keys())
    counts = [ranges[label]["violations"] for label in labels]
    fig, ax = plt.subplots(figsize=(4.5, 1.5))
    ax.barh(labels, counts, color="#c53030")
    ax.set_title("Range Violations", fontsize=8)
    ax.tick_params(axis="both", labelsize=7)
    fig.tight_layout()
    return _figure_to_data_uri(fig)


def render_html(payload: Dict[str, object]) -> str:
    def _metrics_table(stats: Dict[str, object]) -> str:
        drift = stats.get("drift_secs") or {}
        return (
            "<table class='metrics'>"
            f"<tr><th>Missing rate</th><td>{stats.get('missing_rate', 0):.2%}</td></tr>"
            f"<tr><th>Late rate</th><td>{stats.get('late_rate', 0):.2%}</td></tr>"
            f"<tr><th>Outlier rate</th><td>{stats.get('outlier_rate', 0):.2%}</td></tr>"
            f"<tr><th>Drift mean</th><td>{drift.get('mean', 0.0):.3f}s</td></tr>"
            f"<tr><th>Drift p95</th><td>{drift.get('p95', 0.0):.3f}s</td></tr>"
            f"<tr><th>Drift max</th><td>{drift.get('max', 0.0):.3f}s</td></tr>"
            "</table>"
        )

    def _section(name: str, data: Dict[str, object]) -> str:
        stats = data.get("stats", {})
        issues = data.get("issues", [])
        issue_list = "".join(f"<li>{issue}</li>" for issue in issues) or "<li>None</li>"
        hist_img = _histogram_image(stats)
        missing_img = _missing_map_image(stats)
        range_img = _range_bar_image(stats)
        chart_defs = [
            (hist_img, "Drift Histogram"),
            (missing_img, "Minute Coverage"),
            (range_img, "Range Violations"),
        ]
        charts = "".join(
            f"<figure><img src='{uri}' alt='{label}'/><figcaption>{label}</figcaption></figure>"
            for uri, label in chart_defs
            if uri
        )
        return (
            f"<section><h2>{name}</h2>"
            f"<div class='grid'>"
            f"<div>{_metrics_table(stats)}</div>"
            f"<div class='charts'>{charts}</div>"
            "</div>"
            f"<h3>Issues</h3><ul>{issue_list}</ul>"
            "</section>"
        )

    config = payload.get("config", {})
    tz = config.get("timezone", "UTC")
    header = (
        f"<header><h1>Janitza QA Report</h1>"
        f"<p>Input: {payload.get('input_csv')}</p>"
        f"<p>Output: {payload.get('output_csv')}</p>"
        f"<p>Timezone: {tz}</p>"
        "</header>"
    )

    repair = payload.get("repair", {})
    repair_summary = (
        "<section><h2>Repair Summary</h2>"
        "<table class='metrics'>"
        f"<tr><th>Generated rows</th><td>{repair.get('generated_rows', 0)}</td></tr>"
        f"<tr><th>Filled cells</th><td>{repair.get('filled_cells', 0)}</td></tr>"
        f"<tr><th>Forward fill limit</th><td>{repair.get('forward_fill_max', '-')}</td></tr>"
        "</table></section>"
    )

    original_section = _section("Original CSV", payload.get("original", {}))
    repaired_section = _section("Repaired CSV", payload.get("repaired", {}))

    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>"
        "body {font-family: Arial, sans-serif; margin: 1.5rem;}"
        "header {margin-bottom: 1.5rem;}"
        "section {margin-bottom: 1.5rem;}"
        ".metrics {border-collapse: collapse;}"
        ".metrics th, .metrics td {border: 1px solid #ccc; padding: 0.3rem 0.6rem;}"
        ".charts figure {display: inline-block; margin-right: 1rem;}"
        ".charts img {max-height: 120px; display: block;}"
        ".charts figcaption {font-size: 0.75rem; color: #555; margin-top: 0.3rem;}"
        ".grid {display: flex; gap: 1rem;}"
        "</style></head><body>"
        f"{header}{repair_summary}{original_section}{repaired_section}"
        "</body></html>"
    )


def write_reports(base_output: Path, payload: Dict[str, object]) -> Dict[str, Path]:
    json_path = Path(f"{base_output}.qa.json")
    html_path = Path(f"{base_output}.qa.html")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    html_content = render_html(payload)
    html_path.write_text(html_content, encoding="utf-8")
    return {"json": json_path, "html": html_path}


def build_payload(
    *,
    config: Dict[str, object],
    input_csv: Path,
    output_csv: Path,
    original: Dict[str, object],
    repaired: Dict[str, object],
    repair: Dict[str, object],
) -> Dict[str, object]:
    return {
        "config": config,
        "input_csv": str(input_csv),
        "output_csv": str(output_csv),
        "original": original,
        "repaired": repaired,
        "repair": repair,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate QA report for Janitza CSV exports.")
    parser.add_argument("input_csv", type=Path, help="Path to input CSV file")
    parser.add_argument("--repair-out", type=Path, required=False, help="Path to write repaired CSV")
    parser.add_argument("--config", type=Path, required=False, help="Override data quality config file path")
    parser.add_argument("--no-repair", action="store_true", help="Skip repair, only validate")
    args = parser.parse_args(argv)

    from . import load_config, validate_csv, auto_repair_csv  # local import to avoid circular

    cfg = load_config(args.config)
    if args.no_repair or args.repair_out is None:
        result = validate_csv(args.input_csv, cfg)
        payload = {
            "config": cfg,
            "input_csv": str(args.input_csv),
            "output_csv": str(args.input_csv),
            "original": result,
            "repaired": result,
            "repair": {},
        }
        write_reports(args.input_csv, payload)
    else:
        auto_repair_csv(args.input_csv, args.repair_out, cfg)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
