from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for

from services.company_service import CompanyService
from services.cost_sheet_service import CostSheetTemplateService
from services.customer_service import BookingService, CustomerService
from services.finance_service import ReceiptService
from services.pdf_service import build_cost_sheet_pdf, build_pdf
from services.project_service import FlatService, ProjectService, TowerService
from services.statement_service import CustomerStatementService
from utils.auth import current_project_id

finance_bp = Blueprint("finance", __name__)


@finance_bp.route("/")
def workspace():
    return render_template("finance.html", title="Finance")


@finance_bp.route("/due-statements")
def due_statements():
    filters = request.args.to_dict()
    filters.setdefault("project_id", current_project_id() or "")
    query = {}
    if filters.get("flat_no"):
        query["flat_no"] = {"$regex": filters["flat_no"], "$options": "i"}
    if filters.get("tower"):
        query["tower"] = filters["tower"]
    if filters.get("project_id"):
        query["project_id"] = filters["project_id"]
    bookings = BookingService.all(query, [("tower", 1), ("flat_no", 1)])
    if filters.get("customer"):
        needle = filters["customer"].lower()
        bookings = [b for b in bookings if needle in (b.get("customer_name") or (CustomerService.get(b.get("customer_id")) or {}).get("name", "")).lower()]
    for booking in bookings:
        if not booking.get("customer_name"):
            customer = CustomerService.get(booking.get("customer_id"))
            booking["customer_name"] = customer.get("name", "") if customer else ""
    return render_template("due_statements.html", title="Due Statements", bookings=bookings, projects=ProjectService.all({}, [("name", 1)]), towers=TowerService.all({}, [("name", 1)]), filters=filters)


@finance_bp.route("/sales-report")
def sales_report():
    query = {"project_id": current_project_id()} if current_project_id() else {}
    bookings = BookingService.all(query, [("created_at", -1)])
    totals = {
        "gross": sum(float(b.get("gross_amount", 0) or 0) for b in bookings),
        "paid": sum(float(b.get("paid_amount", 0) or 0) for b in bookings),
        "due": sum(float(b.get("due_amount", 0) or 0) for b in bookings),
    }
    return render_template("sales_report.html", title="Sales Report", bookings=bookings, totals=totals)


@finance_bp.route("/collection-report")
def collection_report():
    receipts = ReceiptService.recent(500)
    total = sum(float(r.get("amount", 0) or 0) for r in receipts)
    return render_template("collection_report.html", title="Collection Report", receipts=receipts, total=total)


@finance_bp.route("/cost-sheets")
def cost_sheets():
    query = {"project_id": current_project_id()} if current_project_id() else {}
    bookings = BookingService.all(query, [("created_at", -1)])
    return render_template("cost_sheets.html", title="Cost Sheets", bookings=bookings)


@finance_bp.route("/cost-sheet/<booking_id>/pdf")
def cost_sheet_pdf(booking_id):
    return _send_cost_sheet_pdf(booking_id, as_attachment=True)


@finance_bp.route("/cost-sheet/<booking_id>/view")
def cost_sheet_view_pdf(booking_id):
    return _send_cost_sheet_pdf(booking_id, as_attachment=False)


@finance_bp.route("/cost-sheet/<booking_id>/regenerate", methods=["POST"])
def regenerate_cost_sheet(booking_id):
    booking, customer, flat, project, tower = _cost_sheet_context(booking_id)
    CostSheetTemplateService.snapshot_for_booking(booking, customer=customer, flat=flat, project=project, tower=tower, regenerate=True)
    flash("Cost sheet regenerated from the latest master template.", "success")
    return redirect(url_for("inventory.flat_profile", flat_id=booking.get("flat_id")))


def _cost_sheet_context(booking_id):
    booking = BookingService.get(booking_id)
    if not booking:
        abort(404)
    customer = CustomerService.get(booking.get("customer_id"))
    flat = FlatService.get(booking.get("flat_id"))
    project = ProjectService.get(booking.get("project_id"))
    tower = TowerService.get(booking.get("tower_id"))
    return booking, customer, flat, project, tower


def _send_cost_sheet_pdf(booking_id, as_attachment):
    booking, customer, flat, project, tower = _cost_sheet_context(booking_id)
    snapshot = CostSheetTemplateService.snapshot_for_booking(booking, customer=customer, flat=flat, project=project, tower=tower)
    booking["cost_sheet_snapshot"] = snapshot
    pdf = build_cost_sheet_pdf(
        booking,
        customer=customer,
        flat=flat,
        project=project,
        tower=tower,
        company=CompanyService.current(),
        root_path=current_app.root_path,
    )
    return send_file(pdf, mimetype="application/pdf", as_attachment=as_attachment, download_name=f"cost-sheet-{booking.get('flat_no', 'flat')}.pdf")


@finance_bp.route("/customer-statements")
def customer_statements():
    term = request.args.get("q", "").strip().lower()
    query = {"project_id": current_project_id()} if current_project_id() else {}
    bookings = BookingService.all(query, [("created_at", -1)])
    if term:
        bookings = [
            booking for booking in bookings
            if term in (booking.get("customer_name") or "").lower()
            or term in (booking.get("flat_no") or "").lower()
            or term in (booking.get("tower") or "").lower()
        ]
    return render_template("customer_statements.html", title="Customer Statements", bookings=bookings, q=request.args.get("q", ""))


@finance_bp.route("/customer-statement/<booking_id>")
def customer_statement(booking_id):
    statement = CustomerStatementService.build(booking_id)
    if not statement:
        abort(404)
    return render_template("customer_statement.html", title="Customer Cost & Collection Statement", statement=statement)


@finance_bp.route("/due-statement/<booking_id>/pdf")
def due_pdf(booking_id):
    booking = BookingService.get(booking_id)
    rows = [
        ["Particular", "Amount"],
        ["Flat", booking.get("flat_no", "")],
        ["Gross Amount", f"{booking.get('gross_amount', 0):,.2f}"],
        ["Paid Amount", f"{booking.get('paid_amount', 0):,.2f}"],
        ["Due Amount", f"{booking.get('due_amount', 0):,.2f}"],
        ["GST", f"{booking.get('gst', 0):,.2f}"],
        ["Corpus Fund", f"{booking.get('corpus_fund', 0):,.2f}"],
        ["TDS", f"{booking.get('tds', 0):,.2f}"],
    ]
    pdf = build_pdf("Due Statement", rows, CompanyService.display_name(current_app.config["COMPANY_NAME"]))
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=f"due-statement-{booking.get('flat_no', 'flat')}.pdf")


@finance_bp.route("/receipt/<receipt_id>/pdf")
def receipt_pdf(receipt_id):
    receipt = ReceiptService.get(receipt_id)
    rows = [
        ["Particular", "Details"],
        ["Receipt No", receipt.get("receipt_no", "")],
        ["Date", receipt.get("date", "")],
        ["Customer", receipt.get("customer_name", "")],
        ["Flat", receipt.get("flat_no", "")],
        ["Payment Mode", receipt.get("payment_mode", "")],
        ["Amount", f"{receipt.get('amount', 0):,.2f}"],
        ["Receipt Against", receipt.get("receipt_against", "")],
    ]
    if receipt.get("payment_mode") == "Cheque":
        rows += [
            ["Cheque No", receipt.get("cheque_no", "")],
            ["Cheque Date", receipt.get("cheque_date", "")],
            ["Bank", receipt.get("bank", "")],
            ["Branch", receipt.get("branch", "")],
            ["Status", receipt.get("receipt_status", "Pending")],
        ]
    elif receipt.get("payment_mode") in {"NEFT", "RTGS", "IMPS"}:
        rows += [
            ["UTR No", receipt.get("utr_number", "")],
            ["Transaction Date", receipt.get("transaction_date", "")],
            ["Bank", receipt.get("bank", "")],
            ["Branch", receipt.get("branch", "")],
        ]
    elif receipt.get("payment_mode") == "Card / POS":
        rows += [
            ["Reference No", receipt.get("reference_number", "")],
            ["Bank", receipt.get("bank", "")],
        ]
    rows += [
        ["Remarks", receipt.get("remarks", "")],
    ]
    pdf = build_pdf("Receipt", rows, CompanyService.display_name(current_app.config["COMPANY_NAME"]))
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=f"{receipt.get('receipt_no', 'receipt')}.pdf")
