from datetime import datetime
from math import ceil
import re

from flask import Blueprint, render_template, request

from database.mongo import get_db
from services.customer_service import BookingService, CustomerService
from services.finance_service import ReceiptService
from services.project_service import FlatService, ProjectService, TowerService
from utils.auth import current_project_id
from utils.formatters import serialize_doc

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


def _numeric(field):
    return {"$convert": {"input": field, "to": "double", "onError": 0, "onNull": 0}}


def _combine_match(*parts):
    parts = [part for part in parts if part]
    if not parts:
        return {}
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


def _date_match(fields, start, end):
    if not start and not end:
        return {}

    clauses = []
    for field in fields:
        datetime_range = {}
        iso_range = {}
        if start:
            datetime_range["$gte"] = start
            iso_range["$gte"] = start.strftime("%Y-%m-%d")
        if end:
            datetime_range["$lte"] = end
            iso_range["$lte"] = end.strftime("%Y-%m-%d")
        clauses.append({field: datetime_range})
        clauses.append({field: iso_range})
    return {"$or": clauses}


def _serialize_many(rows):
    return [serialize_doc(row) for row in rows]


def _first_facet_count(facet):
    return facet[0]["count"] if facet else 0


def _customer_search_query(term):
    base_query = {"project_id": current_project_id()} if current_project_id() else {}
    if term:
        regex = {"$regex": re.escape(term), "$options": "i"}
        base_query = {
            **base_query,
            "$or": [
                {"name": regex},
                {"phone": regex},
                {"aadhaar": regex},
                {"pan": regex},
            ],
        }
    return CustomerService.scoped_query(base_query)


@dashboard_bp.route("/")
def index():
    db = get_db()
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

    flat_match = FlatService.scoped_query(flat_query)
    flat_aggregate = list(db.flats.aggregate([
        {"$match": flat_match},
        {"$facet": {
            "status_counts": [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            ],
            "tower_counts": [
                {"$group": {
                    "_id": "$tower_id",
                    "total": {"$sum": 1},
                    "sold": {"$sum": {"$cond": [{"$eq": ["$status", "Sold"]}, 1, 0]}},
                    "available": {"$sum": {"$cond": [{"$eq": ["$status", "Available"]}, 1, 0]}},
                }},
            ],
            "registration_status": [
                {"$match": {"status": "Registered"}},
                {"$count": "count"},
            ],
            "total": [
                {"$count": "count"},
            ],
        }},
    ]))[0]
    flat_status_counts = {row["_id"] or "Unknown": row["count"] for row in flat_aggregate["status_counts"]}
    flats_by_tower = {row["_id"]: row for row in flat_aggregate["tower_counts"]}
    total_flats = _first_facet_count(flat_aggregate["total"])
    sold_flats = flat_status_counts.get("Sold", 0)
    available_flats = flat_status_counts.get("Available", 0)
    registered_status_flats = _first_facet_count(flat_aggregate["registration_status"])

    booking_query = {}
    if filters.get("project_id"):
        booking_query["project_id"] = filters["project_id"]
    if filters.get("tower_id"):
        booking_query["tower_id"] = filters["tower_id"]
    booking_match = BookingService.scoped_query(booking_query)
    if filters.get("flat_status"):
        flat_ids = db.flats.distinct("_id", flat_match)
        booking_match["flat_id"] = {"$in": [str(flat_id) for flat_id in flat_ids]}
    if filters.get("customer"):
        booking_match["customer_name"] = {"$regex": re.escape(filters["customer"]), "$options": "i"}
    booking_match = _combine_match(booking_match, _date_match(["booked_at", "created_at"], start, end))

    due_positive = {"$expr": {"$gt": [_numeric("$due_amount"), 0]}}
    due_paid = {"$expr": {"$lte": [_numeric("$due_amount"), 0]}}
    booking_aggregate = list(db.bookings.aggregate([
        {"$match": booking_match},
        {"$facet": {
            "summary": [
                {"$group": {
                    "_id": None,
                    "total_sales": {"$sum": _numeric("$gross_amount")},
                    "outstanding": {"$sum": _numeric("$due_amount")},
                }},
            ],
            "booked_flats": [
                {"$match": {"flat_id": {"$nin": [None, ""]}}},
                {"$group": {"_id": "$flat_id"}},
                {"$count": "count"},
            ],
            "pending_count": [
                {"$match": due_positive},
                {"$count": "count"},
            ],
            "pending_customers": [
                {"$match": due_positive},
                {"$group": {"_id": {"$ifNull": ["$customer_id", "$customer_name"]}}},
                {"$count": "count"},
            ],
            "active_customers": [
                {"$match": {"customer_id": {"$nin": [None, ""]}}},
                {"$group": {"_id": "$customer_id"}},
                {"$count": "count"},
            ],
            "fully_paid_customers": [
                {"$match": _combine_match(due_paid, {"customer_id": {"$nin": [None, ""]}})},
                {"$group": {"_id": "$customer_id"}},
                {"$count": "count"},
            ],
            "pending_due_customers": [
                {"$match": _combine_match(due_positive, {"customer_id": {"$nin": [None, ""]}})},
                {"$group": {"_id": "$customer_id"}},
                {"$count": "count"},
            ],
            "pending_top": [
                {"$match": due_positive},
                {"$addFields": {"due_amount_sort": _numeric("$due_amount")}},
                {"$sort": {"due_amount_sort": -1}},
                {"$limit": 5},
            ],
            "recent": [
                {"$sort": {"created_at": -1}},
                {"$limit": 5},
            ],
        }},
    ]))[0]
    booking_summary = booking_aggregate["summary"][0] if booking_aggregate["summary"] else {}
    total_sales = _amount(booking_summary.get("total_sales"))
    outstanding = _amount(booking_summary.get("outstanding"))
    booked_flats = _first_facet_count(booking_aggregate["booked_flats"])
    pending_count = _first_facet_count(booking_aggregate["pending_count"])
    pending_bookings = _serialize_many(booking_aggregate["pending_top"])
    recent_bookings = _serialize_many(booking_aggregate["recent"])

    receipt_booking_scoped = bool(filters.get("project_id") or filters.get("tower_id") or filters.get("customer"))
    receipt_query = {}
    if receipt_booking_scoped:
        if filters.get("project_id"):
            receipt_query["project_id"] = filters["project_id"]
        if filters.get("tower_id"):
            receipt_query["tower_id"] = filters["tower_id"]
        if filters.get("customer"):
            receipt_query["customer_name"] = {"$regex": re.escape(filters["customer"]), "$options": "i"}
    receipt_match = _combine_match(ReceiptService.scoped_query(receipt_query), _date_match(["date", "created_at"], start, end))
    receipt_aggregate = list(db.receipts.aggregate([
        {"$match": receipt_match},
        {"$facet": {
            "summary": [
                {"$group": {
                    "_id": None,
                    "total_received": {"$sum": _numeric("$amount")},
                }},
            ],
            "registration_flats": [
                {"$match": {"receipt_against": "Registration Charges", "flat_id": {"$nin": [None, ""]}}},
                {"$group": {"_id": "$flat_id"}},
                {"$count": "count"},
            ],
            "recent_registrations": [
                {"$match": {"receipt_against": "Registration Charges"}},
                {"$sort": {"created_at": -1}},
                {"$limit": 5},
                {"$project": {"customer_name": 1, "flat_no": 1, "date": 1}},
            ],
            "recent": [
                {"$sort": {"created_at": -1}},
                {"$limit": 5},
            ],
        }},
    ]))[0]
    receipt_summary = receipt_aggregate["summary"][0] if receipt_aggregate["summary"] else {}
    total_received = _amount(receipt_summary.get("total_received"))
    registered_flats = registered_status_flats + _first_facet_count(receipt_aggregate["registration_flats"])
    recent_receipts = _serialize_many(receipt_aggregate["recent"])

    customer_query = _customer_search_query(filters.get("customer", ""))
    customer_aggregate = list(db.customers.aggregate([
        {"$match": customer_query},
        {"$facet": {
            "total": [{"$count": "count"}],
            "recent": [
                {"$sort": {"created_at": -1}},
                {"$limit": 5},
            ],
        }},
    ]))[0]
    total_customers = _first_facet_count(customer_aggregate["total"])
    recent_customers = _serialize_many(customer_aggregate["recent"])

    collection_efficiency = _pct(total_received, total_sales)
    sales_progress = _pct(sold_flats, total_flats)
    inventory_movement = _pct(sold_flats + booked_flats, total_flats)
    pending_registrations = max((sold_flats or booked_flats) - registered_flats, 0)
    health_score = round((sales_progress + collection_efficiency + inventory_movement) / 3)
    health_status = "Excellent" if health_score >= 90 else "Good" if health_score >= 75 else "Attention Needed" if health_score >= 50 else "Critical"

    tower_query = {"project_id": filters["project_id"]} if filters.get("project_id") else {}
    all_towers = _serialize_many(db.towers.find(TowerService.scoped_query(tower_query), {"project": 1, "name": 1}).sort([("project", 1), ("name", 1)]))
    tower_booking_rows = list(db.bookings.aggregate([
        {"$match": booking_match},
        {"$group": {
            "_id": "$tower_id",
            "revenue": {"$sum": _numeric("$gross_amount")},
        }},
    ]))
    bookings_by_tower = {row["_id"]: row for row in tower_booking_rows}
    tower_receipt_rows = list(db.receipts.aggregate([
        {"$match": receipt_match},
        {"$group": {
            "_id": "$tower_id",
            "collected": {"$sum": _numeric("$amount")},
        }},
    ]))
    receipts_by_tower = {row["_id"]: row for row in tower_receipt_rows}
    tower_rows = []
    for tower in all_towers:
        tower_flat_counts = flats_by_tower.get(tower["_id"], {})
        tower_booking_counts = bookings_by_tower.get(tower["_id"], {})
        tower_receipt_counts = receipts_by_tower.get(tower["_id"], {})
        revenue = _amount(tower_booking_counts.get("revenue"))
        collected = _amount(tower_receipt_counts.get("collected"))
        sold = tower_flat_counts.get("sold", 0)
        total = tower_flat_counts.get("total", 0)
        progress = _pct(sold, total)
        tower_rows.append({
            "name": tower.get("name"),
            "project": tower.get("project"),
            "total": total,
            "sold": sold,
            "available": tower_flat_counts.get("available", 0),
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

    pending_summary = {
        "total_outstanding": outstanding,
        "customers_pending": _first_facet_count(booking_aggregate["pending_customers"]),
        "highest": pending_bookings[0] if pending_bookings else None,
        "overdue_customers": _first_facet_count(booking_aggregate["pending_customers"]),
        "top": pending_bookings[:5],
    }
    upcoming = {
        "7": {"amount": 0, "customers": 0},
        "15": {"amount": 0, "customers": 0},
        "30": {"amount": 0, "customers": 0},
    }
    upcoming["7"]["amount"] = outstanding * 0.25
    upcoming["15"]["amount"] = outstanding * 0.5
    upcoming["30"]["amount"] = outstanding
    upcoming["7"]["customers"] = min(ceil(pending_count * 0.25), pending_count)
    upcoming["15"]["customers"] = min(ceil(pending_count * 0.5), pending_count)
    upcoming["30"]["customers"] = pending_count

    alerts = []
    if pending_count:
        alerts.append({"type": "Critical", "label": "Overdue Payments", "count": pending_count, "message": "High-value dues need follow-up."})
    if pending_registrations:
        alerts.append({"type": "Warning", "label": "Pending Registrations", "count": pending_registrations, "message": "Sold units are pending registration."})
    if pending_bookings[:3]:
        alerts.append({"type": "Critical", "label": "High Outstanding Customers", "count": len(pending_bookings[:3]), "message": "Top customer balances need attention."})
    if collection_efficiency < 75 and total_sales:
        alerts.append({"type": "Warning", "label": "Collection Below Target", "count": 1, "message": f"Collection efficiency is {collection_efficiency}%."})
    alerts = alerts[:5]

    recent_registrations = receipt_aggregate["recent_registrations"]
    if not recent_registrations:
        recent_registrations = list(db.flats.find(
            {**flat_match, "status": "Registered"},
            {"flat_no": 1},
        ).limit(5))
        recent_registrations = [{"customer_name": "-", "flat_no": flat.get("flat_no"), "date": "-"} for flat in recent_registrations]

    recent_activity = []
    for booking in recent_bookings:
        recent_activity.append({
            "type": "New Booking",
            "label": booking.get("customer_name") or "Customer",
            "meta": f"{booking.get('flat_no', '-') or '-'} / {booking.get('tower', '-') or '-'}",
            "url": f"/inventory/flat/{booking.get('flat_id')}" if booking.get("flat_id") else "",
            "created_at": booking.get("booked_at") or booking.get("created_at"),
        })
    for receipt in recent_receipts:
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
    for customer in recent_customers:
        recent_activity.append({
            "type": "Customer Added",
            "label": customer.get("name") or "Customer",
            "meta": customer.get("phone") or "-",
            "url": "",
            "created_at": customer.get("created_at"),
        })
    recent_activity = sorted(recent_activity, key=_activity_date, reverse=True)[:5]

    stats = {
        "total_projects": 0,
        "total_towers": len(all_towers),
        "total_flats": total_flats,
        "available_flats": available_flats,
        "booked_flats": booked_flats,
        "sold_flats": sold_flats,
        "registered_flats": registered_flats,
        "total_customers": total_customers,
        "total_sales": total_sales,
        "total_received": total_received,
        "outstanding": outstanding,
        "collection_efficiency": collection_efficiency,
        "inventory_value": total_sales + outstanding,
        "remaining_inventory_value": outstanding,
        "health_score": health_score,
        "health_status": health_status,
        "sales_progress": sales_progress,
        "active_customers": _first_facet_count(booking_aggregate["active_customers"]),
        "fully_paid_customers": _first_facet_count(booking_aggregate["fully_paid_customers"]),
        "pending_due_customers": _first_facet_count(booking_aggregate["pending_due_customers"]),
        "pending_registrations": pending_registrations,
    }
    projects = _serialize_many(db.projects.find(ProjectService.scoped_query({}), {"name": 1}).sort([("name", 1)]))
    stats["total_projects"] = len(projects)
    towers = all_towers

    return render_template(
        "dashboard.html",
        title="Dashboard",
        stats=stats,
        projects=projects,
        towers=towers,
        filters=filters,
        tower_rows=tower_rows,
        tower_summary=tower_summary,
        recent_receipts=recent_receipts,
        recent_bookings=recent_bookings,
        recent_registrations=recent_registrations[:5],
        recent_activity=recent_activity,
        pending_bookings=pending_bookings[:5],
        pending_summary=pending_summary,
        top_outstanding=pending_bookings[:5],
        alerts=alerts,
        upcoming=upcoming,
    )
