"""
SPT Hospital HRMS — Salary Slip PDF Generator
Uses ReportLab to generate professional PDF salary slips.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.payroll import PayrollRecord, PayrollItem, SalarySlip, ComponentType
from app.models.employee import Employee
from app.models.department import Department

logger = logging.getLogger(__name__)

# Colors
PRIMARY_COLOR = colors.HexColor("#0f766e")  # teal-700
DARK_COLOR = colors.HexColor("#0f172a")     # slate-900
LIGHT_GRAY = colors.HexColor("#f8fafc")     # slate-50
MID_GRAY = colors.HexColor("#e2e8f0")       # slate-200


def _num_to_words(n: float) -> str:
    """Convert a number to words (simplified, for salary slip footer)."""
    try:
        n = int(n)
        ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

        def below_thousand(num):
            if num == 0:
                return ""
            elif num < 20:
                return ones[num]
            elif num < 100:
                return tens[num // 10] + (" " + ones[num % 10] if num % 10 != 0 else "")
            else:
                return ones[num // 100] + " Hundred" + (" " + below_thousand(num % 100) if num % 100 != 0 else "")

        if n == 0:
            return "Zero"
        elif n < 1000:
            return below_thousand(n)
        elif n < 100000:
            return below_thousand(n // 1000) + " Thousand" + (" " + below_thousand(n % 1000) if n % 1000 != 0 else "")
        elif n < 10000000:
            return below_thousand(n // 100000) + " Lakh" + (" " + _num_to_words(n % 100000) if n % 100000 != 0 else "")
        else:
            return below_thousand(n // 10000000) + " Crore" + (" " + _num_to_words(n % 10000000) if n % 10000000 != 0 else "")
    except Exception:
        return str(int(n))


async def generate_salary_slip(
    payroll_record_id: int,
    db: AsyncSession,
    generated_by_id: int,
) -> Optional[str]:
    """
    Generate a professional PDF salary slip for a payroll record.
    Returns the file path of the generated PDF.
    """
    # Load payroll record with all related data
    result = await db.execute(
        select(PayrollRecord)
        .where(PayrollRecord.id == payroll_record_id)
        .options(
            selectinload(PayrollRecord.items),
            selectinload(PayrollRecord.employee).selectinload(Employee.department),
            selectinload(PayrollRecord.employee).selectinload(Employee.designation),
            selectinload(PayrollRecord.period),
            selectinload(PayrollRecord.salary_slip),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise ValueError(f"Payroll record {payroll_record_id} not found")

    emp = record.employee
    period = record.period

    # Output path
    slip_dir = os.path.join(settings.UPLOAD_DIR, "salary_slips")
    os.makedirs(slip_dir, exist_ok=True)
    filename = f"salary_slip_{emp.employee_id}_{period.year}_{period.month:02d}.pdf"
    file_path = os.path.join(slip_dir, filename)

    # Build PDF
    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    hospital_name = settings.HOSPITAL_NAME or "SPT Hospital"
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=PRIMARY_COLOR,
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName="Helvetica-Bold",
    )
    sub_header_style = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        fontSize=10,
        textColor=DARK_COLOR,
        alignment=TA_CENTER,
        spaceAfter=2,
    )

    story.append(Paragraph(hospital_name.upper(), header_style))
    story.append(Paragraph("Payroll Salary Slip", sub_header_style))
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY_COLOR))
    story.append(Spacer(1, 3 * mm))

    # Slip title
    title_style = ParagraphStyle(
        "SlipTitle",
        parent=styles["Normal"],
        fontSize=12,
        textColor=DARK_COLOR,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    story.append(Paragraph(f"Salary Slip for {period.period_name}", title_style))
    story.append(Spacer(1, 4 * mm))

    # ── Employee Information ───────────────────────────────────────────────────
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=9,
                                  textColor=colors.HexColor("#64748b"), fontName="Helvetica")
    value_style = ParagraphStyle("Value", parent=styles["Normal"], fontSize=9,
                                  textColor=DARK_COLOR, fontName="Helvetica-Bold")

    emp_data = [
        [Paragraph("Employee Name", label_style), Paragraph(emp.full_name, value_style),
         Paragraph("Employee Code", label_style), Paragraph(emp.employee_id, value_style)],
        [Paragraph("Department", label_style),
         Paragraph(emp.department.name if emp.department else "-", value_style),
         Paragraph("Designation", label_style),
         Paragraph(emp.designation.name if emp.designation else "-", value_style)],
        [Paragraph("Biometric Code", label_style),
         Paragraph(str(emp.biometric_code or "-"), value_style),
         Paragraph("Pay Period", label_style),
         Paragraph(period.period_name, value_style)],
        [Paragraph("Joining Date", label_style),
         Paragraph(str(emp.joining_date or "-"), value_style),
         Paragraph("Generated On", label_style),
         Paragraph(datetime.now().strftime("%d-%b-%Y"), value_style)],
    ]

    emp_table = Table(emp_data, colWidths=[35 * mm, 55 * mm, 35 * mm, 55 * mm])
    emp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 4 * mm))

    # ── Attendance Summary ─────────────────────────────────────────────────────
    att_data = [
        ["Working Days", "Present Days", "Absent Days", "Leave Days", "OT Hours"],
        [
            str(record.total_working_days),
            str(round(record.present_days, 1)),
            str(round(record.absent_days, 1)),
            str(round(record.leave_days, 1)),
            f"{record.ot_hours:.2f}",
        ],
    ]
    att_table = Table(att_data, colWidths=[36 * mm] * 5)
    att_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(att_table)
    story.append(Spacer(1, 4 * mm))

    # ── Earnings & Deductions ──────────────────────────────────────────────────
    earnings = [(i.component_name, round(i.amount, 2)) for i in record.items
                if i.component_type == ComponentType.EARNING]
    deductions = [(i.component_name, round(i.amount, 2)) for i in record.items
                  if i.component_type == ComponentType.DEDUCTION]

    # Make same length
    max_rows = max(len(earnings), len(deductions))
    while len(earnings) < max_rows:
        earnings.append(("", ""))
    while len(deductions) < max_rows:
        deductions.append(("", ""))

    header_style_white = ParagraphStyle("HeaderWhite", parent=styles["Normal"],
                                         fontSize=10, textColor=colors.white,
                                         fontName="Helvetica-Bold", alignment=TA_CENTER)

    earn_ded_data = [
        [Paragraph("EARNINGS", header_style_white), "", Paragraph("DEDUCTIONS", header_style_white), ""],
        ["Component", "Amount (₹)", "Component", "Amount (₹)"],
    ]
    for i in range(max_rows):
        earn_ded_data.append([
            earnings[i][0],
            f"₹ {earnings[i][1]:,.2f}" if earnings[i][1] != "" else "",
            deductions[i][0],
            f"₹ {deductions[i][1]:,.2f}" if deductions[i][1] != "" else "",
        ])

    total_earn = sum(a for _, a in earnings if isinstance(a, (int, float)))
    total_ded = sum(a for _, a in deductions if isinstance(a, (int, float)))

    earn_ded_data.append([
        Paragraph("<b>GROSS SALARY</b>", ParagraphStyle("Bold", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold")),
        Paragraph(f"<b>₹ {record.gross_salary:,.2f}</b>", ParagraphStyle("BoldR", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph("<b>TOTAL DEDUCTIONS</b>", ParagraphStyle("Bold", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold")),
        Paragraph(f"<b>₹ {record.total_deductions:,.2f}</b>", ParagraphStyle("BoldR", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
    ])

    col_w = [55 * mm, 25 * mm, 55 * mm, 25 * mm]
    earn_ded_table = Table(earn_ded_data, colWidths=col_w)
    earn_ded_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("SPAN", (2, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (1, 0), PRIMARY_COLOR),
        ("BACKGROUND", (2, 0), (3, 0), DARK_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), MID_GRAY),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0fdf4")),
    ]))
    story.append(earn_ded_table)
    story.append(Spacer(1, 4 * mm))

    # ── Net Salary ─────────────────────────────────────────────────────────────
    net_style = ParagraphStyle("Net", parent=styles["Normal"], fontSize=12,
                                textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER)
    net_data = [
        [Paragraph(f"NET SALARY: ₹ {record.net_salary:,.2f}", net_style)],
        [Paragraph(f"({_num_to_words(record.net_salary)} Rupees Only)", sub_header_style)],
    ]
    net_table = Table(net_data, colWidths=[180 * mm])
    net_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#ccfbf1")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
    ]))
    story.append(net_table)
    story.append(Spacer(1, 10 * mm))

    # ── Signature Area ─────────────────────────────────────────────────────────
    sig_data = [
        ["Employee Signature", "", "Authorized Signatory"],
        ["________________________", "", "________________________"],
        ["Date: _______________", "", hospital_name],
    ]
    sig_table = Table(sig_data, colWidths=[60 * mm, 60 * mm, 60 * mm])
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#64748b")),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 4 * mm))

    # Footer
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7,
                                   textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("This is a computer generated salary slip and does not require a physical signature.", footer_style))

    doc.build(story)

    # Save slip record
    existing_slip_result = await db.execute(
        select(SalarySlip).where(SalarySlip.payroll_record_id == payroll_record_id)
    )
    existing_slip = existing_slip_result.scalar_one_or_none()
    if existing_slip:
        existing_slip.file_path = file_path
        existing_slip.generated_at = datetime.now(timezone.utc)
        existing_slip.generated_by_id = generated_by_id
    else:
        slip = SalarySlip(
            payroll_record_id=payroll_record_id,
            file_path=file_path,
            generated_by_id=generated_by_id,
        )
        db.add(slip)

    await db.commit()
    logger.info(f"Generated salary slip: {file_path}")
    return file_path
