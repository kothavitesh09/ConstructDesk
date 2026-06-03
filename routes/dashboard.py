from datetime import datetime
from math import ceil

from flask import Blueprint, render_template, request

from services.customer_service import BookingService, CustomerService
from services.finance_service import ReceiptService
from services.project_service import FlatService, ProjectService, TowerService
from utils.auth import current_project_id

dashboard_bp = Blueprint("dashboard", __name__)


def _amount(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _date(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value)[:10], fmt)
        except ValueError:
            continue
    return None


def _pct(part, total):
    return round((part / total * 100), 1) if total else 0


def _activity_date(item):
    return _date(item.get("date") or item.get("booked_at") or item.get("created_at")) or datetime.min


def _matches_date_range(value, start, end):
    parsed = _date(value)
    if not parsed:
        return not start and not end
    if start and parsed < start:
        return False
    if end and parsed > end:
        return False
    return True


@dashboard_bp.route("/")
def index():
    filters = request.args.to_dict()
    filters.setdefault("project_id", current_project_id() or "")
    start = _date(filters.get("date_from"))
    end = _date(filters.get("date_to"))

    flat_query = {}
    if filters.get("project_id"):
        flat_query["project_id"] = filters["project_id"]
    if filters.get("tower_id"):
        flat_query["tower_id"] = filters["tower_id"]
    if filters.get("flat_status"):
        flat_query["status"] = filters["flat_status"]

    flats = FlatService.all(flat_query, [("tower", 1), ("floor", 1), ("flat_no", 1)])
    flat_ids = {flat["_id"] for flat in flats}
    flats_by_id = {flat["_id"]: flat for flat in flats}

    booking_query = {}
    if filters.get("project_id"):
        booking_query["project_id"] = filters["project_id"]
    if filters.get("tower_id"):
        booking_query["tower_id"] = filters["tower_id"]
    bookings = BookingService.all(booking_query, [("created_at", -1)])
    if flat_query:
        bookings = [booking for booking in bookings if booking.get("flat_id") in flat_ids]
    if filters.get("customer"):
        needle = filters["customer"].lower()
        bookings = [booking for booking in bookings if needle in (booking.get("customer_name") or "").lower()]
    if start or end:
        bookings = [booking for booking in bookings if _matches_date_range(booking.get("booked_at") or booking.get("created_at"), start, end)]
    booking_ids = {booking["_id"] for booking in bookings}

    receipt_booking_scoped = bool(filters.get("project_id") or filters.get("tower_id") or filters.get("customer"))
    receipts = ReceiptService.all({}, [("created_at", -1)])
    receipts = [
        receipt for receipt in receipts
        if (not receipt_booking_scoped or receipt.get("booking_id") in booking_ids)
        and _matches_date_range(receipt.get("date") or receipt.get("created_at"), start, end)
    ]

    customers = CustomerService.search(filters.get("customer", ""), limit=500)
    total_sales = sum(_amount(booking.get("gross_amount")) for booking in bookings)
    total_received = sum(_amount(receipt.get("amount")) for receipt in receipts)
    outstanding = sum(_amount(booking.get("due_amount")) for booking in bookings)
    sold_flats = sum(1 for flat in flats if flat.get("status") == "Sold")
    available_flats = sum(1 for flat in flats if flat.get("status") == "Available")
    booked_flats = len({booking.get("flat_id") for booking in bookings if booking.get("flat_id")})
    registration_receipt_flats = {receipt.get("flat_id") for receipt in receipts if receipt.get("receipt_against") == "Registration Charges"}
    registered_flats = sum(1 for flat in flats if flat.get("status") == "Registered") + len(registration_receipt_flats)

    collection_efficiency = _pct(total_received, total_sales)
    sales_progress = _pct(sold_flats, len(flats))
    inventory_movement = _pct(sold_flats + booked_flats, len(flats))
    pending_registrations = max((sold_flats or booked_flats) - registered_flats, 0)
    health_score = round((sales_progress + collection_efficiency + inventory_movement) / 3)
    health_status = "Excellent" if health_score >= 90 else "Good" if health_score >= 75 else "Attention Needed" if health_score >= 50 else "Critical"

    tower_query = {"project_id": filters["project_id"]} if filters.get("project_id") else {}
    all_towers = TowerService.all(tower_query, [("project", 1), ("name", 1)])
    tower_rows = []
    for tower in all_towers:
        tower_flats = [flat for flat in flats if flat.get("tower_id") == tower["_id"]]
        tower_bookings = [booking for booking in bookings if booking.get("tower_id") == tower["_id"]]
        tower_booking_ids = {booking["_id"] for booking in tower_bookings}
        tower_receipts = [receipt for receipt in receipts if receipt.get("booking_id") in tower_booking_ids or receipt.get("tower") == tower.get("name")]
        revenue = sum(_amount(booking.get("gross_amount")) for booking in tower_bookings)
        collected = sum(_amount(receipt.get("amount")) for receipt in tower_receipts)
        sold = sum(1 for flat in tower_flats if flat.get("status") == "Sold")
        progress = _pct(sold, len(tower_flats))
        tower_rows.append({
            "name": tower.get("name"),
            "project": tower.get("project"),
            "total": len(tower_flats),
            "sold": sold,
            "available": sum(1 for flat in tower_flats if flat.get("status") == "Available"),
            "progress": progress,
            "collection_pct": _pct(collected, revenue),
            "revenue": revenue,
        })
    tower_rows = sorted(tower_rows, key=lambda row: (row["progress"], row["sold"], row["total"]), reverse=True)
    tower_summary = {
        "total": len(all_towers),
        "best": tower_rows[0] if tower_rows else None,
        "average_progress": round(sum(row["progress"] for row in tower_rows) / len(tower_rows), 1) if tower_rows else 0,
    }

    pending_bookings = sorted([booking for booking in bookings if _amount(booking.get("due_amount")) > 0], key=lambda item: _amount(item.get("due_amount")), reverse=True)
    pending_customer_ids = {booking.get("customer_id") or booking.get("customer_name") for booking in pending_bookings}
    pending_customer_ids.discard(None)
    pending_summary = {
        "total_outstanding": outstanding,
        "customers_pending": len(pending_customer_ids),
        "highest": pending_bookings[0] if pending_bookings else None,
        "overdue_customers": len(pending_customer_ids),
        "top": pending_bookings[:5],
    }
    upcoming = {
        "7": {"amount": 0, "customers": 0},
        "15": {"amount": 0, "customers": 0},
        "30": {"amount": 0, "customers": 0},
    }
    pending_count = len(pending_bookings)
    for booking in pending_bookings:
        due = _amount(booking.get("due_amount"))
        upcoming["7"]["amount"] += due * 0.25
        upcoming["15"]["amount"] += due * 0.5
        upcoming["30"]["amount"] += due
    upcoming["7"]["customers"] = min(ceil(pending_count * 0.25), pending_count)
    upcoming["15"]["customers"] = min(ceil(pending_count * 0.5), pending_count)
    upcoming["30"]["customers"] = pending_count

    alerts = []
    if pending_bookings:
        alerts.append({"type": "Critical", "label": "Overdue Payments", "count": len(pending_bookings), "message": "High-value dues need follow-up."})
    if pending_registrations:
        alerts.append({"type": "Warning", "label": "Pending Registrations", "count": pending_registrations, "message": "Sold units are pending registration."})
    if pending_bookings[:3]:
        alerts.append({"type": "Critical", "label": "High Outstanding Customers", "count": len(pending_bookings[:3]), "message": "Top customer balances need attention."})
    if collection_efficiency < 75 and total_sales:
        alerts.append({"type": "Warning", "label": "Collection Below Target", "count": 1, "message": f"Collection efficiency is {collection_efficiency}%."})
    alerts = alerts[:5]

    recent_registrations = []
    for receipt in receipts:
        if receipt.get("receipt_against") == "Registration Charges":
            recent_registrations.append({
                "customer_name": receipt.get("customer_name"),
                "flat_no": receipt.get("flat_no"),
                "date": receipt.get("date") or "-",
            })
    if not recent_registrations:
        recent_registrations = [
            {"customer_name": "-", "flat_no": flat.get("flat_no"), "date": "-"}
            for flat in flats
            if flat.get("status") == "Registered"
        ]

    recent_activity = []
    for booking in bookings:
        recent_activity.append({
            "type": "New Booking",
            "label": booking.get("customer_name") or "Customer",
            "meta": f"{booking.get('flat_no', '-') or '-'} / {booking.get('tower', '-') or '-'}",
            "url": f"/inventory/flat/{booking.get('flat_id')}" if booking.get("flat_id") else "",
            "created_at": booking.get("booked_at") or booking.get("created_at"),
        })
    for receipt in receipts:
        recent_activity.append({
            "type": "Payment Received",
            "label": receipt.get("customer_name") or "Customer",
            "meta": f"{receipt.get('flat_no', '-') or '-'} / {_amount(receipt.get('amount')):,.0f}",
            "url": f"/receipts/?booking_id={receipt.get('booking_id')}" if receipt.get("booking_id") else "/receipts/",
            "created_at": receipt.get("date") or receipt.get("created_at"),
        })
    for registration in recent_registrations:
        recent_activity.append({
            "type": "Registration Completed",
            "label": registration.get("customer_name") or "Customer",
            "meta": registration.get("flat_no") or "-",
            "url": "",
            "created_at": registration.get("date"),
        })
    for customer in customers[:5]:
        recent_activity.append({
            "type": "Customer Added",
            "label": customer.get("name") or "Customer",
            "meta": customer.get("phone") or "-",
            "url": "",
            "created_at": customer.get("created_at"),
        })
    recent_activity = sorted(recent_activity, key=_activity_date, reverse=True)[:5]

    stats = {
        "total_projects": len(ProjectService.all()),
        "total_towers": len(all_towers),
        "total_flats": len(flats),
        "available_flats": available_flats,
        "booked_flats": booked_flats,
        "sold_flats": sold_flats,
        "registered_flats": registered_flats,
        "total_customers": len(customers),
        "total_sales": total_sales,
        "total_received": total_received,
        "outstanding": outstanding,
        "collection_efficiency": collection_efficiency,
        "inventory_value": total_sales + outstanding,
        "remaining_inventory_value": outstanding,
        "health_score": health_score,
        "health_status": health_status,
        "sales_progress": sales_progress,
        "active_customers": len({booking.get("customer_id") for booking in bookings if booking.get("customer_id")}),
        "fully_paid_customers": len({booking.get("customer_id") for booking in bookings if _amount(booking.get("due_amount")) == 0}),
        "pending_due_customers": len({booking.get("customer_id") for booking in pending_bookings if booking.get("customer_id")}),
        "pending_registrations": pending_registrations,
    }

    return render_template(
        "dashboard.html",
        title="Dashboard",
        stats=stats,
        projects=ProjectService.all({}, [("name", 1)]),
        towers=TowerService.all({"project_id": filters["project_id"]}, [("name", 1)]) if filters.get("project_id") else TowerService.all({}, [("name", 1)]),
        filters=filters,
        tower_rows=tower_rows,
        tower_summary=tower_summary,
        recent_receipts=receipts[:5],
        recent_bookings=bookings[:5],
        recent_registrations=recent_registrations[:5],
        recent_activity=recent_activity,
        pending_bookings=pending_bookings[:5],
        pending_summary=pending_summary,
        top_outstanding=pending_bookings[:5],
        alerts=alerts,
        upcoming=upcoming,
    )
