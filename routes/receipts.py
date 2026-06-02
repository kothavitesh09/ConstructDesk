from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.customer_service import BookingService, CustomerService
from services.finance_service import ReceiptService
from services.project_service import FlatService

receipts_bp = Blueprint("receipts", __name__)


def _receipt_form_data(form):
    return {
        "date": form.get("date"),
        "amount": float(form.get("amount") or 0),
        "basic": float(form.get("basic") or 0),
        "gst": float(form.get("gst") or 0),
        "tds": float(form.get("tds") or 0),
        "bank": form.get("bank"),
        "branch": form.get("branch"),
        "cheque_no": form.get("cheque_no"),
        "cheque_date": form.get("cheque_date"),
        "utr_number": form.get("utr_number"),
        "transaction_date": form.get("transaction_date"),
        "reference_number": form.get("reference_number"),
        "payment_mode": form.get("payment_mode"),
        "receipt_against": form.get("receipt_against"),
        "receipt_status": form.get("receipt_status"),
        "remarks": form.get("remarks"),
    }


def _receipt_context(receipt):
    booking = BookingService.get(receipt.get("booking_id"))
    customer = CustomerService.get(receipt.get("customer_id") or (booking or {}).get("customer_id"))
    flat = FlatService.get(receipt.get("flat_id") or (booking or {}).get("flat_id"))
    return {
        "receipt": receipt,
        "customer": customer or {},
        "booking": booking or {},
        "flat": flat or {},
    }


def _unique_receipt_contexts(*groups):
    seen = set()
    contexts = []
    for group in groups:
        for receipt in group or []:
            receipt_id = receipt.get("_id")
            if receipt_id in seen:
                continue
            seen.add(receipt_id)
            contexts.append(_receipt_context(receipt))
    return contexts


@receipts_bp.route("/", methods=["GET", "POST"])
def index():
    selected = None
    booking = None
    customer = None
    if request.method == "POST":
        booking = BookingService.get(request.form["booking_id"])
        customer = CustomerService.get(booking["customer_id"])
        receipt_data = _receipt_form_data(request.form)
        receipt_data.update({
            "booking_id": booking["_id"],
            "customer_id": booking["customer_id"],
            "flat_id": booking["flat_id"],
            "project_id": booking.get("project_id"),
            "tower_id": booking.get("tower_id"),
            "customer_name": customer["name"],
            "flat_no": booking["flat_no"],
            "tower": booking["tower"],
        })
        ReceiptService.create_receipt(receipt_data)
        flash("Receipt saved and outstanding updated.", "success")
        return redirect(url_for("receipts.index", booking_id=booking["_id"]))

    booking_id = request.args.get("booking_id")
    if booking_id:
        booking = BookingService.get(booking_id)
        customer = CustomerService.get(booking["customer_id"]) if booking else None
        flat = FlatService.get(booking["flat_id"]) if booking else None
        previous_receipts = ReceiptService.all({"booking_id": booking_id}, [("date", -1)]) if booking else []
        selected = {"booking": booking, "customer": customer, "flat": flat, "receipts": previous_receipts}

    bookings = BookingService.all({}, [("created_at", -1)])
    for item in bookings:
        if not item.get("customer_name"):
            item_customer = CustomerService.get(item.get("customer_id"))
            item["customer_name"] = item_customer.get("name", "") if item_customer else ""
    recent_receipts = ReceiptService.recent(12)
    selected_receipts = selected["receipts"] if selected else []
    receipt_details = _unique_receipt_contexts(selected_receipts, recent_receipts)
    return render_template("receipts.html", title="Receipts", bookings=bookings, selected=selected, recent_receipts=recent_receipts, receipt_details=receipt_details, receipt_no_preview=ReceiptService.next_receipt_no())


@receipts_bp.post("/<receipt_id>/edit")
def edit(receipt_id):
    receipt = ReceiptService.get(receipt_id)
    if not receipt:
        abort(404)
    ReceiptService.update_receipt(receipt_id, _receipt_form_data(request.form))
    flash("Receipt updated.", "success")
    return redirect(url_for("receipts.index", booking_id=receipt.get("booking_id")))


@receipts_bp.post("/<receipt_id>/status")
def status(receipt_id):
    receipt = ReceiptService.get(receipt_id)
    if not receipt:
        abort(404)
    if ReceiptService.update_status(receipt_id, request.form.get("receipt_status")):
        flash("Receipt status updated.", "success")
    else:
        flash("Invalid receipt status.", "danger")
    return redirect(url_for("receipts.index", booking_id=receipt.get("booking_id")))
