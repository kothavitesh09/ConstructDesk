from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _serif_font_names():
    regular_name = "Times-Roman"
    bold_name = "Times-Bold"
    windows_fonts = Path("C:/Windows/Fonts")
    regular_path = windows_fonts / "georgia.ttf"
    bold_path = windows_fonts / "georgiab.ttf"
    if regular_path.exists() and bold_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("BuilderSerif", str(regular_path)))
            pdfmetrics.registerFont(TTFont("BuilderSerif-Bold", str(bold_path)))
            regular_name = "BuilderSerif"
            bold_name = "BuilderSerif-Bold"
        except Exception:
            pass
    return regular_name, bold_name


def build_pdf(title, rows, company_name="ConstructDesk ERP"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(company_name, styles["Title"]),
        Paragraph(title, styles["Heading2"]),
        Spacer(1, 14),
    ]
    table = Table(rows, colWidths=[170, 320])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer


def build_cost_sheet_pdf(booking, customer=None, flat=None, project=None, tower=None, company=None, root_path=None):
    customer = customer or {}
    flat = flat or {}
    project = project or {}
    tower = tower or {}
    company = company or {}
    general = company.get("general", {}) or {}
    costing = project.get("costing", {}) or {}
    sheet = booking.get("cost_sheet", {}) or {}
    snapshot = booking.get("cost_sheet_snapshot", {}) or {}
    template = snapshot.get("template", {}) or {}
    snapshot_amounts = snapshot.get("amounts", {}) or {}

    def number(*keys, default=0):
        for source in (snapshot_amounts, booking, sheet, template, costing, flat, project, tower):
            for key in keys:
                value = source.get(key) if isinstance(source, dict) else None
                if value not in (None, ""):
                    try:
                        return float(value or 0)
                    except (TypeError, ValueError):
                        return default
        return default

    def configured_number(*keys, default=0):
        for source in (template, costing, sheet, booking, project, flat, tower):
            for key in keys:
                value = source.get(key) if isinstance(source, dict) else None
                if value not in (None, ""):
                    try:
                        return float(value or 0)
                    except (TypeError, ValueError):
                        return default
        return default

    def text(*values):
        for value in values:
            if value not in (None, ""):
                return str(value)
        return ""

    def money(value):
        return f"\u20b9 {float(value or 0):,.2f}"

    def qty(value):
        return f"{float(value or 0):,.0f}"

    sft = number("sft")
    floor = number("floor")
    base_rate = configured_number("base_price_per_sft", "rate_per_sft")
    infrastructure_rate = configured_number("infrastructure_per_sft", "infrastructure_rate", "infrastructure_charges_per_sft", "infrastructure_per_sft")
    floor_rise_rate = configured_number("floor_rise_per_sft_per_floor", "floor_rise_rate", "floor_rise")
    east_facing_rate = configured_number("facing_charges_per_sft", "east_facing_rate", "east_facing_charges_per_sft")
    clubhouse_rate = configured_number("clubhouse_per_sft", "clubhouse_rate", "clubhouse_charges_per_sft")
    corpus_rate = configured_number("corpus_fund_per_sft", "corpus_rate")

    base_price = number("base_price", default=sft * base_rate)
    infrastructure = number("infrastructure_charges", default=sft * infrastructure_rate)
    parking = number("parking")
    floor_rise = number("floor_rise_amount", default=sft * floor * floor_rise_rate)
    facing = text(booking.get("facing"), flat.get("facing")).lower()
    east_facing = number("east_facing_charges", default=sft * east_facing_rate if facing == "east" else number("facing_charges"))
    clubhouse = number("clubhouse", "clubhouse_charges", default=sft * clubhouse_rate)
    sale_total = base_price + infrastructure + parking + floor_rise + east_facing + clubhouse
    sale_gst_percent = configured_number("sale_gst_percent", "gst_percent", default=5)
    sale_gst = number("gst", default=sale_total * sale_gst_percent / 100)
    sale_sub_total = sale_total + sale_gst

    other_charges = number("other_charges")
    legal = number("legal_documentation", "legal_documentation_charges")
    maintenance = number("maintenance_deposit")
    additional_total = other_charges + legal + maintenance
    additional_gst_percent = configured_number("additional_gst_percent", default=18)
    additional_gst = number("other_gst", default=additional_total * additional_gst_percent / 100)
    additional_sub_total = additional_total + additional_gst

    corpus = number("corpus_fund_amount", default=sft * corpus_rate)
    if corpus == 0:
        corpus = number("corpus_fund")
    if corpus_rate == 0 and sft:
        corpus_rate = corpus / sft
    grand_total = sale_sub_total + additional_sub_total + corpus
    if snapshot_amounts:
        base_price = float(snapshot_amounts.get("base_price", base_price) or 0)
        infrastructure = float(snapshot_amounts.get("infrastructure_charges", infrastructure) or 0)
        parking = float(snapshot_amounts.get("parking", parking) or 0)
        floor_rise = float(snapshot_amounts.get("floor_rise", floor_rise) or 0)
        east_facing = float(snapshot_amounts.get("facing_charges", east_facing) or 0)
        clubhouse = float(snapshot_amounts.get("clubhouse", clubhouse) or 0)
        sale_total = float(snapshot_amounts.get("sale_total", sale_total) or 0)
        sale_gst = float(snapshot_amounts.get("gst", sale_gst) or 0)
        sale_sub_total = float(snapshot_amounts.get("sale_sub_total", sale_sub_total) or 0)
        other_charges = float(snapshot_amounts.get("other_charges", other_charges) or 0)
        legal = float(snapshot_amounts.get("legal_documentation", legal) or 0)
        maintenance = float(snapshot_amounts.get("maintenance_deposit", maintenance) or 0)
        additional_total = float(snapshot_amounts.get("additional_total", additional_total) or 0)
        additional_gst = float(snapshot_amounts.get("other_gst", additional_gst) or 0)
        additional_sub_total = float(snapshot_amounts.get("additional_sub_total", additional_sub_total) or 0)
        corpus = float(snapshot_amounts.get("corpus_fund", corpus) or 0)
        grand_total = float(snapshot_amounts.get("grand_total", snapshot_amounts.get("gross_amount", grand_total)) or 0)

    configured_schedule = (
        snapshot.get("payment_schedule")
        or booking.get("payment_schedule")
        or sheet.get("payment_schedule")
        or project.get("payment_schedule")
        or costing.get("payment_schedule")
    )
    default_stages = [
        "Booking Advance",
        "Within 60 Days",
        "Foundation Completion",
        "Plinth Completion",
        "Slab Completion",
        "Brick Work Completion",
        "Plastering Completion",
        "Flooring Completion",
        "Painting Completion",
        "Handover / Possession",
    ]
    if isinstance(configured_schedule, dict):
        configured_schedule = configured_schedule.get("stages") or configured_schedule.get("rows") or []
    if configured_schedule:
        payment_rows = [
            {
                "stage": item.get("stage") or item.get("name") or item.get("payment_schedule") or "",
                "percentage": float(item.get("percentage") or item.get("percent") or 0),
                "value": item.get("value"),
                "gst": item.get("gst"),
                "total": item.get("total"),
            }
            for item in configured_schedule
        ]
    else:
        payment_rows = [{"stage": stage, "percentage": 10.0} for stage in default_stages]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()
    regular_font, bold_font = _serif_font_names()
    ink = colors.HexColor("#111111")
    muted = colors.HexColor("#555555")
    line = colors.HexColor("#8C8C8C")
    section_fill = colors.HexColor("#E9E9E9")
    soft_fill = colors.HexColor("#F7F7F7")
    alt_fill = colors.HexColor("#FAFAFA")
    normal = ParagraphStyle("CostSheetNormal", parent=styles["Normal"], fontName=regular_font, fontSize=9, leading=11, textColor=ink)
    bold = ParagraphStyle("CostSheetBold", parent=normal, fontName=bold_font)
    small = ParagraphStyle("CostSheetSmall", parent=normal, fontSize=8.4, leading=10)
    small_bold = ParagraphStyle("CostSheetSmallBold", parent=small, fontName="Times-Bold")
    header_company = ParagraphStyle("CostSheetCompany", parent=bold, alignment=1, fontSize=13, leading=15)
    header_project = ParagraphStyle("CostSheetProject", parent=normal, alignment=1, fontSize=10, leading=12, textColor=muted)
    center_title = ParagraphStyle("CostSheetTitle", parent=bold, alignment=1, fontSize=18, leading=21)
    section_heading = ParagraphStyle("CostSheetSection", parent=bold, alignment=1, fontSize=11.5, leading=13.5)
    grand_label = ParagraphStyle("CostSheetGrandLabel", parent=bold, fontSize=13.5, leading=16)
    grand_value = ParagraphStyle("CostSheetGrandValue", parent=grand_label, alignment=2)
    right = ParagraphStyle("CostSheetRight", parent=normal, alignment=2)
    right_bold = ParagraphStyle("CostSheetRightBold", parent=bold, alignment=2)
    center = ParagraphStyle("CostSheetCenter", parent=normal, alignment=1)
    center_bold = ParagraphStyle("CostSheetCenterBold", parent=bold, alignment=1)

    page_width = A4[0] - doc.leftMargin - doc.rightMargin
    base_table = [
        ("BOX", (0, 0), (-1, -1), 0.8, line),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONTNAME", (0, 0), (-1, -1), regular_font),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]
    cell_lines = [
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D0D0")),
    ]

    def p(value, style=normal):
        return Paragraph(str(value or ""), style)

    def section_table(rows, col_widths=None, extra_style=None, heights=None):
        table = Table(rows, colWidths=col_widths or [page_width / len(rows[0])] * len(rows[0]), rowHeights=heights)
        table.setStyle(TableStyle(base_table + (extra_style or [])))
        return table

    def logo_flowable():
        logo_path = general.get("logo_path")
        if not logo_path or not root_path:
            return None
        candidate = Path(root_path) / "static" / logo_path
        if not candidate.exists():
            return None
        logo = Image(str(candidate))
        max_width, max_height = 92, 42
        ratio = min(max_width / logo.imageWidth, max_height / logo.imageHeight)
        logo.drawWidth = logo.imageWidth * ratio
        logo.drawHeight = logo.imageHeight * ratio
        logo.hAlign = "CENTER"
        return logo

    header_items = []
    logo = logo_flowable()
    if logo:
        header_items.append(logo)
        header_items.append(Spacer(1, 4))
    header_items.extend([
        Paragraph(text(general.get("company_name"), "ConstructDesk ERP"), header_company),
        Paragraph(text(project.get("name"), flat.get("project"), booking.get("project")), header_project),
        Spacer(1, 8),
        Paragraph("COST SHEET", center_title),
    ])
    header = Table([[header_items]], colWidths=[page_width])
    header.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    story = [header]
    info_widths = [90, 92, 90, 92, 90, 92]
    story.append(section_table([
        [p("Customer Name :", bold), p(text(customer.get("name"), booking.get("customer_name"))), p("S/W/D/o :", bold), p(text(customer.get("relation_name"), customer.get("guardian_name"))), p("Address :", bold), p(text(customer.get("address")))],
        [p("Mobile No :", bold), p(text(customer.get("phone"), customer.get("mobile"))), p("Email ID :", bold), p(text(customer.get("email"))), p("", bold), p("")],
        [p("Aadhaar No :", bold), p(text(customer.get("aadhaar"))), p("PAN No :", bold), p(text(customer.get("pan"))), p("", bold), p("")],
        [p("Flat No :", bold), p(text(flat.get("flat_no"), booking.get("flat_no"))), p("Floor :", bold), p(text(flat.get("floor"), booking.get("floor"))), p("SFT :", bold), p(qty(sft))],
        [p("Tower Name :", bold), p(text(tower.get("name"), flat.get("tower"), booking.get("tower"))), p("Facing :", bold), p(text(flat.get("facing"), booking.get("facing"))), p("Type :", bold), p(text(flat.get("type"), booking.get("type")))],
        [p("Project Name :", bold), p(text(project.get("name"), flat.get("project"), booking.get("project"))), p("Area :", bold), p(text(project.get("area"), flat.get("area"), booking.get("area"))), p("", bold), p("")],
    ], info_widths, cell_lines + [
        ("LINEABOVE", (0, 3), (-1, 3), 0.8, line),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
    ], heights=[22, 22, 22, 22, 22, 22]))
    story.append(Spacer(1, 8))

    calc_widths = [290, 105, 148]
    calc_rows = [
        [p("COST PARTICULARS", section_heading), p(""), p("")],
        [p("Particulars", bold), p("Rate", center_bold), p("Amount", right_bold)],
        [p("Base Price"), p(money(base_rate), right), p(money(base_price), right)],
        [p("Infrastructure Charges per SFT"), p(money(infrastructure_rate), right), p(money(infrastructure), right)],
        [p("Car Parking"), p(""), p(money(parking), right)],
        [p("Floor Rise Charges"), p(money(floor_rise_rate), right), p(money(floor_rise), right)],
        [p("East Facing Charges per SFT"), p(money(east_facing_rate), right), p(money(east_facing), right)],
        [p("Club House Charges per SFT"), p(money(clubhouse_rate), right), p(money(clubhouse), right)],
        [p("Total", bold), p(""), p(money(sale_total), right_bold)],
        [p(f"Add GST @ {sale_gst_percent:g}%", bold), p(f"{sale_gst_percent:.2f}%", center_bold), p(money(sale_gst), right_bold)],
        [p("Sub Total (Including GST)", bold), p("A", center_bold), p(money(sale_sub_total), right_bold)],
    ]
    story.append(section_table(calc_rows, calc_widths, [
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), section_fill),
        ("BACKGROUND", (0, 1), (-1, 1), soft_fill),
        ("INNERGRID", (0, 1), (-1, -1), 0.35, colors.HexColor("#D7D7D7")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, line),
        ("FONTNAME", (0, 0), (-1, 0), bold_font),
        ("LINEABOVE", (0, 8), (-1, 8), 0.6, line),
        ("LINEABOVE", (0, 10), (-1, 10), 0.8, line),
    ], heights=[18, 17] + [16] * (len(calc_rows) - 2)))
    story.append(Spacer(1, 8))

    additional_rows = [
        [p("ADDITIONAL CHARGES", section_heading), p(""), p("")],
        [p("Particulars", bold), p("Rate", center_bold), p("Amount", right_bold)],
        [p("Other Charges"), p(""), p(money(other_charges), right)],
        [p("Legal and Documentation Charges"), p(""), p(money(legal), right)],
        [p("Maintenance Deposit"), p(""), p(money(maintenance), right)],
        [p("Total", bold), p(""), p(money(additional_total), right_bold)],
        [p(f"Add GST @ {additional_gst_percent:g}%", bold), p(f"{additional_gst_percent:.2f}%", center_bold), p(money(additional_gst), right_bold)],
        [p("Sub Total (Including GST)", bold), p("B", center_bold), p(money(additional_sub_total), right_bold)],
        [p("Interest Free Corpus Fund per SFT (C)", bold), p(money(corpus_rate), right_bold), p(money(corpus), right_bold)],
        [p("Grand Total (A + B + C)", grand_label), p("", grand_label), p(money(grand_total), grand_value)],
    ]
    story.append(section_table(additional_rows, calc_widths, [
        ("SPAN", (0, 0), (-1, 0)),
        ("SPAN", (0, 9), (1, 9)),
        ("BACKGROUND", (0, 0), (-1, 0), section_fill),
        ("BACKGROUND", (0, 1), (-1, 1), soft_fill),
        ("BACKGROUND", (0, 9), (-1, 9), colors.HexColor("#EFEFEF")),
        ("INNERGRID", (0, 1), (-1, 8), 0.35, colors.HexColor("#D7D7D7")),
        ("LINEABOVE", (0, 5), (-1, 5), 0.6, line),
        ("LINEABOVE", (0, 7), (-1, 7), 0.8, line),
        ("BOX", (0, 9), (-1, 9), 1.8, ink),
        ("LINEABOVE", (0, 9), (-1, 9), 1.8, ink),
        ("LINEBELOW", (0, 9), (-1, 9), 1.8, ink),
        ("FONTNAME", (0, 0), (-1, 0), bold_font),
    ], heights=[18, 17] + [16] * 7 + [24]))
    story.append(Spacer(1, 8))

    note_rows = [[p("Notes", bold)]]
    for note in snapshot.get("notes") or template.get("notes") or [
        "GST applicable as per prevailing rates.",
        "Registration charges shall be borne by the purchaser.",
        "Government taxes are subject to change.",
        "Any increase in statutory charges shall be extra.",
    ]:
        note_rows.append([p(f"\u2022 {note}", small)])
    story.append(section_table(note_rows, [page_width], [
        ("BACKGROUND", (0, 0), (-1, 0), soft_fill),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, line),
        ("TOPPADDING", (0, 1), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2.5),
    ], heights=[16] + [12] * (len(note_rows) - 1)))
    story.append(Spacer(1, 8))

    schedule = [
        [p("PAYMENT SCHEDULE", section_heading), p(""), p(""), p(""), p("")],
        [p("Payment Schedule", bold), p("Percentage", center_bold), p("Value", right_bold), p("GST", right_bold), p("Total", right_bold)],
    ]
    for row in payment_rows:
        percent = float(row.get("percentage") or 0)
        total = float(row.get("total")) if row.get("total") not in (None, "") else grand_total * percent / 100
        value = float(row.get("value")) if row.get("value") not in (None, "") else (total / (1 + sale_gst_percent / 100) if total and sale_gst_percent else total)
        gst = float(row.get("gst")) if row.get("gst") not in (None, "") else total - value
        schedule.append([p(row.get("stage"), small), p(f"{percent:.2f}%", center), p(money(value), right), p(money(gst), right), p(money(total), right)])
    payment_styles = [
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), section_fill),
        ("BACKGROUND", (0, 1), (-1, 1), soft_fill),
        ("INNERGRID", (0, 1), (-1, -1), 0.35, colors.HexColor("#D7D7D7")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, line),
        ("FONTNAME", (0, 0), (-1, 0), bold_font),
    ]
    for idx in range(2, len(schedule)):
        if idx % 2 == 0:
            payment_styles.append(("BACKGROUND", (0, idx), (-1, idx), alt_fill))
    story.append(section_table(schedule, [190, 78, 105, 78, 92], payment_styles, heights=[18, 17] + [15] * (len(schedule) - 2)))
    story.append(Spacer(1, 8))

    story.append(section_table([
        [p("Declaration", bold)],
        [p(snapshot.get("terms_conditions") or template.get("terms_conditions") or "I have read and understood the above terms and conditions and agree to the payment schedule.")],
    ], [page_width], [
        ("BACKGROUND", (0, 0), (-1, 0), soft_fill),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, line),
        ("TOPPADDING", (0, 1), (-1, 1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ], heights=[16, 28]))
    story.append(Spacer(1, 38))
    story.append(section_table([
        [p("Customer Signature", center_bold), p("Company Authorized Signatory", center_bold)],
    ], [page_width / 2, page_width / 2], [
        ("LINEABOVE", (0, 0), (0, 0), 0.9, ink),
        ("LINEABOVE", (1, 0), (1, 0), 0.9, ink),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0, colors.white),
    ], heights=[18]))

    doc.build(story)
    buffer.seek(0)
    return buffer
