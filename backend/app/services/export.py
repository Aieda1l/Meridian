"""Export service — CSV and PDF report generation with column filtering."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.core.config import settings


# Ordered definition of all available columns.
# key → (CSV header, PDF header, dict key)
ALL_COLUMNS = [
    ("member_number",    "Member Number", "Member #"),
    ("name",             "Name",          "Name"),
    ("role",             "Role",          "Role"),
    ("date",             "Date",          "Date"),
    ("check_in_time",    "Check-In Time", "In"),
    ("check_out_time",   "Check-Out Time","Out"),
    ("duration_minutes", "Duration (min)", "Dur(min)"),
    ("method",           "Method",        "Method"),
    ("status",           "Status",        "Status"),
    ("flag_reason",      "Flag Reason",   "Flag"),
]


def _filter_columns(
    columns: set[str] | None,
) -> list[tuple[str, str, str]]:
    """Return the ordered list of (key, csv_header, pdf_header) to include."""
    if columns is None:
        return ALL_COLUMNS
    return [c for c in ALL_COLUMNS if c[0] in columns]


def generate_csv(
    sessions: list[dict],
    member_totals: list[dict],
    *,
    columns: set[str] | None = None,
    include_summary: bool = True,
) -> bytes:
    """Generate a UTF-8 CSV with BOM for Excel compatibility.

    ``columns`` is an optional set of column keys to include (default: all).
    """
    active = _filter_columns(columns)
    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel

    writer = csv.writer(output)
    writer.writerow([h for _, h, _ in active])

    for s in sessions:
        writer.writerow([s.get(key, "") for key, _, _ in active])

    if include_summary:
        writer.writerow([])
        writer.writerow(["SUMMARY"])
        writer.writerow(["Member Number", "Name", "Total Hours"])
        for mt in member_totals:
            hours = mt.get("total_minutes", 0) / 60.0
            writer.writerow([
                mt.get("member_number", ""),
                mt.get("name", ""),
                f"{hours:.1f}",
            ])

    return output.getvalue().encode("utf-8")


def generate_pdf(
    sessions: list[dict],
    member_totals: list[dict],
    season_name: str,
    *,
    columns: set[str] | None = None,
    include_summary: bool = True,
) -> bytes:
    """Generate a PDF report using reportlab with optional column filtering."""
    active = _filter_columns(columns)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph(f"<b>{settings.TEAM_NAME}</b>", styles["Title"]))
    elements.append(Paragraph(f"Season: {season_name}", styles["Heading2"]))
    elements.append(Paragraph(f"Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    elements.append(Spacer(1, 0.3*inch))

    # Session table
    headers = [ph for _, _, ph in active]
    data = [headers]

    # Find the duration column index for alignment (if present)
    dur_idx: int | None = None
    for i, (key, _, _) in enumerate(active):
        if key == "duration_minutes":
            dur_idx = i
            break

    current_member = None
    member_subtotal = 0

    for s in sessions:
        if current_member and current_member != s.get("member_number"):
            # Subtotal row
            sub_row = [""] * len(active)
            if dur_idx is not None:
                sub_row[dur_idx] = str(member_subtotal)
            # Put label in the last column or second-to-last
            label_idx = min(len(active) - 1, max(dur_idx + 1 if dur_idx is not None else 0, 0))
            sub_row[label_idx] = f"Subtotal: {current_member}"
            data.append(sub_row)
            member_subtotal = 0

        current_member = s.get("member_number")
        dur = s.get("duration_minutes", 0) or 0
        member_subtotal += dur

        row = []
        for key, _, _ in active:
            val = s.get(key, "")
            if key == "name":
                val = (val or "")[:20]
            elif key == "flag_reason":
                val = (val or "")[:15]
            elif key == "duration_minutes":
                val = str(val)
            row.append(val)
        data.append(row)

    # Final subtotal
    if current_member:
        sub_row = [""] * len(active)
        if dur_idx is not None:
            sub_row[dur_idx] = str(member_subtotal)
        label_idx = min(len(active) - 1, max(dur_idx + 1 if dur_idx is not None else 0, 0))
        sub_row[label_idx] = f"Subtotal: {current_member}"
        data.append(sub_row)

    if len(data) > 1:
        table = Table(data, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A72")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("FONTNAME", (0, 1), (-1, -1), "Courier"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F0F0")]),
        ]
        if dur_idx is not None:
            style_cmds.append(("ALIGN", (dur_idx, 0), (dur_idx, -1), "RIGHT"))
        table.setStyle(TableStyle(style_cmds))
        elements.append(table)

    # Summary section
    if include_summary:
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("<b>Member Hour Totals</b>", styles["Heading2"]))

        summary_data = [["Member #", "Name", "Total Hours"]]
        sorted_totals = sorted(member_totals, key=lambda x: x.get("total_minutes", 0), reverse=True)
        for mt in sorted_totals:
            hours = mt.get("total_minutes", 0) / 60.0
            summary_data.append([mt.get("member_number", ""), mt.get("name", ""), f"{hours:.1f}"])

        if len(summary_data) > 1:
            summary_table = Table(summary_data, repeatRows=1)
            summary_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A72")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Courier"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ]))
            elements.append(summary_table)

    doc.build(elements)
    return buf.getvalue()
