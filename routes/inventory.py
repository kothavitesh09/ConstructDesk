from flask import Blueprint, render_template, request

from services.cost_sheet_service import CostSheetTemplateService
from services.customer_service import BookingService, CustomerService
from services.finance_service import ReceiptService
from services.project_service import FlatService, ProjectService, TowerService
from utils.auth import current_project_id
from utils.formatters import serialize_doc

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/")
def index():
    filters = request.args.to_dict()
    filters.setdefault("project_id", current_project_id() or "")
    project_id = filters.get("project_id")
    flat_filter_keys = ("tower_id", "status", "flat_no", "facing", "floor", "sft_min", "sft_max", "price_min", "price_max")
    should_load_flats = bool(project_id and (filters.get("load") == "1" or any(filters.get(key) for key in flat_filter_keys)))
    flats = FlatService.filter(filters) if should_load_flats else []
    bookings_by_flat = {}
    if flats:
        flat_ids = [flat["_id"] for flat in flats]
        bookings = BookingService.all({"flat_id": {"$in": flat_ids}})
        bookings_by_flat = {booking.get("flat_id"): booking for booking in bookings}
        for flat in flats:
            flat["booking"] = bookings_by_flat.get(flat["_id"])
    return render_template(
        "inventory.html",
        title="Inventory",
        flats=flats,
        projects=ProjectService.all({}, [("name", 1)]),
        towers=FlatService.tower_summaries(project_id) if project_id else [],
        selected_project=ProjectService.get(project_id) if project_id else None,
        project_stats=FlatService.status_summary(project_id) if project_id else {"total": 0, "available": 0, "sold": 0, "blocked": 0, "reserved": 0, "cancelled": 0},
        filters=filters,
        should_load_flats=should_load_flats,
    )


@inventory_bp.route("/flat/<flat_id>")
def flat_profile(flat_id):
    flat = FlatService.get(flat_id)
    booking = serialize_doc(BookingService.by_flat(flat_id)) if flat else None
    customer = CustomerService.get(booking["customer_id"]) if booking else None
    receipts = ReceiptService.all({"flat_id": flat_id}, [("date", -1)])
    gross = float(booking.get("gross_amount", 0)) if booking else 0
    paid = sum(float(r.get("amount", 0) or 0) for r in receipts)
    due = max(gross - paid, 0)
    cost_sheet = CostSheetTemplateService.snapshot_for_booking(booking, customer=customer, flat=flat, project=ProjectService.get(flat.get("project_id")), tower=TowerService.get(flat.get("tower_id"))) if booking else None
    return render_template("flat_profile.html", title=f"Flat {flat['flat_no']}", flat=flat, booking=booking, customer=customer, receipts=receipts, gross=gross, paid=paid, due=due, cost_sheet=cost_sheet)
