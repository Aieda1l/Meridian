"""Export service — CSV and PDF report generation."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.core.config import settings


def generate_csv(
    sessions: list[dict],
    member_totals: list[dict],
) -> bytes:
    """Generate a UTF-8 CSV with BOM for Excel compatibility.

    One row per session. Summary rows at the bottom for each member's total.
    Columns: Member Number, Name, Role, Date, Check-In Time, Check-Out Time,
             Duration (min), Method, Status, Flag Reason
    """
    output = io.StringIO()
    # UTF-8 BOM for Excel
    output.write('\ufeff')

    writer = csv.writer(output)
    writer.writerow([
        "Member Number", "Name", "Role", "Date", "Check-In Time",
        "Check-Out Time", "Duration (min)", "Method", "Status", "Flag Reason"
    ])

    for s in sessions:
        writer.writerow([
            s.get("member_number", ""),
            s.get("name", ""),
            s.get("role", ""),
            s.get("date", ""),
            s.get("check_in_time", ""),
            s.get("check_out_time", ""),
            s.get("duration_minutes", ""),
            s.get("method", ""),
            s.get("status", ""),
            s.get("flag_reason", ""),
        ])

    # Summary rows
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
) -> bytes:
    """Generate a PDF report using reportlab.

    Header with team name, season name, export date.
    Table with session data. Member subtotals. Final summary page.
    """
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
    headers = ["Member #", "Name", "Role", "Date", "In", "Out", "Dur(min)", "Method", "Status", "Flag"]
    data = [headers]

    current_member = None
    member_subtotal = 0

    for s in sessions:
        if current_member and current_member != s.get("member_number"):
            # Insert subtotal row
            data.append(["", "", "", "", "", "", str(member_subtotal), "", f"Subtotal: {current_member}", ""])
            member_subtotal = 0
        current_member = s.get("member_number")
        dur = s.get("duration_minutes", 0) or 0
        member_subtotal += dur

        data.append([
            s.get("member_number", ""),
            s.get("name", "")[:20],  # truncate for table fit
            s.get("role", ""),
            s.get("date", ""),
            s.get("check_in_time", ""),
            s.get("check_out_time", ""),
            str(dur),
            s.get("method", ""),
            s.get("status", ""),
            (s.get("flag_reason", "") or "")[:15],
        ])

    # Final subtotal
    if current_member:
        data.append(["", "", "", "", "", "", str(member_subtotal), "", f"Subtotal: {current_member}", ""])

    if len(data) > 1:
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A72")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("FONTNAME", (0, 1), (-1, -1), "Courier"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F0F0")]),
            ("ALIGN", (6, 0), (6, -1), "RIGHT"),
        ]))
        elements.append(table)

    # Summary page
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
