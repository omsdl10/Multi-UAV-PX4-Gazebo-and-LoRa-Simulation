#!/usr/bin/env python3
"""Generate a polished PDF from PROJECT_REPORT.md."""

from __future__ import annotations

import html
import csv
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.textlabels import Label
from reportlab.graphics.shapes import Drawing

try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
except Exception:  # pragma: no cover - optional dependency
    svg2rlg = None
    renderPM = None


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "PROJECT_REPORT.md"
OUTPUT_DIR = ROOT / "output" / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
OUTPUT = OUTPUT_DIR / "multi_uav_px4_gazebo_lora_project_report.pdf"
PLOT_DIR = ROOT / "analysis" / "output"


def make_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#18212f"),
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#566070"),
            spaceAfter=28,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1Report",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#152238"),
            spaceBefore=16,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2Report",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#243b5a"),
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyReport",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=13.2,
            alignment=TA_LEFT,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletReport",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.1,
            leading=12.5,
            leftIndent=0,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeReport",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=7.2,
            leading=9.2,
            leftIndent=8,
            rightIndent=8,
            backColor=colors.HexColor("#f3f5f8"),
            borderPadding=6,
            spaceBefore=4,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Footer",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            textColor=colors.HexColor("#6d7480"),
        )
    )
    return styles


def clean_inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = text.replace("↔", "&lt;-&gt;").replace("→", "-&gt;").replace("↓", "-&gt;")
    text = text.replace("─", "-").replace("┐", "+").replace("┼", "+").replace("┘", "+")
    return text


def flush_bullets(story, bullets, styles):
    if not bullets:
        return
    items = [
        ListItem(Paragraph(clean_inline(item), styles["BulletReport"]), leftIndent=10)
        for item in bullets
    ]
    story.append(
        ListFlowable(
            items,
            bulletType="bullet",
            start="circle",
            leftIndent=16,
            bulletFontSize=6,
            spaceAfter=6,
        )
    )
    bullets.clear()


def build_story(styles):
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    story = []
    bullets = []
    in_code = False
    code_lines = []

    title = lines[0].lstrip("# ").strip() if lines else "Project Report"
    story.append(Spacer(1, 1.25 * inch))
    story.append(Paragraph(clean_inline(title), styles["ReportTitle"]))
    story.append(
        Paragraph(
            "Multi-UAV PX4, Gazebo, and LoRa Simulation<br/>Generated from PROJECT_REPORT.md",
            styles["ReportSubtitle"],
        )
    )
    story.append(Spacer(1, 0.2 * inch))
    story.append(
        Paragraph(
            "This PDF summarizes the completed simulation architecture, macOS environment, "
            "PX4/Gazebo setup, LoRa communication layer, mission scripts, logging outputs, "
            "paper potential, and current limitations.",
            styles["BodyReport"],
        )
    )
    story.append(PageBreak())

    for raw in lines[1:]:
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                wrapped = []
                for code_line in code_lines:
                    if len(code_line) <= 94:
                        wrapped.append(code_line)
                    else:
                        wrapped.extend(textwrap.wrap(code_line, width=94, replace_whitespace=False))
                story.append(Preformatted("\n".join(wrapped), styles["CodeReport"]))
                code_lines.clear()
                in_code = False
            else:
                flush_bullets(story, bullets, styles)
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            flush_bullets(story, bullets, styles)
            story.append(Spacer(1, 3))
            continue

        if line.startswith("# "):
            flush_bullets(story, bullets, styles)
            story.append(Paragraph(clean_inline(line[2:].strip()), styles["H1Report"]))
        elif line.startswith("## "):
            flush_bullets(story, bullets, styles)
            story.append(Paragraph(clean_inline(line[3:].strip()), styles["H1Report"]))
        elif line.startswith("### "):
            flush_bullets(story, bullets, styles)
            story.append(Paragraph(clean_inline(line[4:].strip()), styles["H2Report"]))
        elif line.startswith("- "):
            bullets.append(line[2:].strip())
        else:
            flush_bullets(story, bullets, styles)
            story.append(Paragraph(clean_inline(line), styles["BodyReport"]))

    flush_bullets(story, bullets, styles)
    add_plot_appendix(story, styles)
    return story


def convert_svg_to_png(svg_path: Path) -> Path | None:
    if svg2rlg is None or renderPM is None:
        return None
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out = TMP_DIR / f"{svg_path.stem}.png"
    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        return None
    renderPM.drawToFile(drawing, str(out), fmt="PNG")
    return out


def add_plot_appendix(story, styles):
    experiment_csv = PLOT_DIR / "lora_experiments.csv"
    if not experiment_csv.exists():
        return

    rows = []
    with experiment_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append({key: float(value) for key, value in row.items()})
    if not rows:
        return

    story.append(PageBreak())
    story.append(Paragraph("Appendix: LoRa Experiment Plots", styles["H1Report"]))
    story.append(
        Paragraph(
            "The following figures were generated from analysis/output/lora_experiments.csv.",
            styles["BodyReport"],
        )
    )

    chart_specs = [
        ("Distance vs RSSI", "rssi", "RSSI (dBm)"),
        ("Distance vs SNR", "snr", "SNR (dB)"),
        ("Distance vs PDR", "pdr", "PDR"),
        ("Distance vs Latency", "latency_ms", "Latency (ms)"),
        ("Distance vs Packet Loss", "packet_loss", "Packet loss"),
    ]
    for title, key, ylabel in chart_specs:
        story.append(
            KeepTogether(
                [
                    Paragraph(title, styles["H2Report"]),
                    make_line_chart(rows, key, ylabel),
                    Spacer(1, 12),
                ]
            )
        )


def nice_bounds(values):
    low = min(values)
    high = max(values)
    if low == high:
        return low - 1, high + 1
    pad = (high - low) * 0.12
    return low - pad, high + pad


def make_line_chart(rows, key, ylabel):
    width = 455
    height = 245
    drawing = Drawing(width, height)
    data = [(row["distance"], row[key]) for row in rows]
    y_low, y_high = nice_bounds([point[1] for point in data])

    plot = LinePlot()
    plot.x = 58
    plot.y = 42
    plot.width = 360
    plot.height = 160
    plot.data = [data]
    plot.lines[0].strokeColor = colors.HexColor("#275c8f")
    plot.lines[0].strokeWidth = 1.8
    plot.joinedLines = 1
    plot.strokeColor = colors.HexColor("#cfd6e0")
    plot.xValueAxis.valueMin = 0
    plot.xValueAxis.valueMax = 5000
    plot.xValueAxis.valueStep = 1000
    plot.xValueAxis.labels.fontSize = 7
    plot.yValueAxis.valueMin = y_low
    plot.yValueAxis.valueMax = y_high
    plot.yValueAxis.labels.fontSize = 7
    plot.yValueAxis.visibleGrid = 1
    plot.yValueAxis.gridStrokeColor = colors.HexColor("#e7ebf1")
    plot.yValueAxis.gridStrokeWidth = 0.4
    drawing.add(plot)

    xlabel = Label()
    xlabel.setOrigin(238, 12)
    xlabel.setText("Distance (m)")
    xlabel.fontName = "Helvetica"
    xlabel.fontSize = 8
    xlabel.textAnchor = "middle"
    drawing.add(xlabel)

    y_label = Label()
    y_label.setOrigin(14, 126)
    y_label.angle = 90
    y_label.setText(ylabel)
    y_label.fontName = "Helvetica"
    y_label.fontSize = 8
    y_label.textAnchor = "middle"
    drawing.add(y_label)
    return drawing


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d8dde6"))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, A4[1] - 0.55 * inch, A4[0] - doc.rightMargin, A4[1] - 0.55 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#6d7480"))
    canvas.drawString(doc.leftMargin, A4[1] - 0.43 * inch, "Multi-UAV PX4, Gazebo, and LoRa Simulation")
    canvas.drawRightString(A4[0] - doc.rightMargin, 0.38 * inch, f"Page {doc.page}")
    canvas.restoreState()


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing source report: {SOURCE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    styles = make_styles()
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.78 * inch,
        bottomMargin=0.6 * inch,
        title="Multi-UAV PX4, Gazebo, and LoRa Simulation Project Report",
        author="Codex",
    )
    doc.build(build_story(styles), onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
