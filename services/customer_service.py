from datetime import datetime

from bson import ObjectId

from services.base_service import BaseService
from services.project_service import FlatService
from utils.auth import current_project_id


class CustomerService(BaseService):
    collection_name = "customers"
    project_scoped = True

    @classmethod
    def search(cls, term="", limit=50):
        project_id = current_project_id()
        base_query = {"project_id": project_id} if project_id else {}
        if not term:
            return cls.all(base_query, [("created_at", -1)], limit)
        query = {**base_query, "$or": [
            {"name": {"$regex": term, "$options": "i"}},
            {"phone": {"$regex": term, "$options": "i"}},
            {"aadhaar": {"$regex": term, "$options": "i"}},
            {"pan": {"$regex": term, "$options": "i"}},
        ]}
        return cls.all(query, [("name", 1)], limit)


class BookingService(BaseService):
    collection_name = "bookings"
    project_scoped = True

    @classmethod
    def calculate_cost(cls, flat, costing=None):
        if costing is None:
            from services.cost_sheet_service import CostSheetTemplateService

            return CostSheetTemplateService.calculate_amounts(flat)
        costing = costing or {}
        sft = float(flat.get("sft", 0) or 0)
        rate = float(costing.get("rate_per_sft", 0) or 0)
        floor = float(flat.get("floor", 0) or 0)
        floor_rise_rate = float(costing.get("floor_rise", 0) or 0)
        floor_rise = sft * floor * floor_rise_rate
        parking = float(costing.get("parking", 0) or 0)
        clubhouse = float(costing.get("clubhouse", 0) or 0)
        facing_charges = float(costing.get("facing_charges", 0) or 0)
        corpus_fund = float(costing.get("corpus_fund", 0) or 0)
        base_price = sft * rate
        taxable = base_price + floor_rise + parking + clubhouse + facing_charges
        gst_percent = float(costing.get("gst_percent", 0) or 0)
        gst = taxable * gst_percent / 100
        gross = taxable + corpus_fund + gst
        return {
            "rate_per_sft": rate,
            "base_price": base_price,
            "floor_rise": floor_rise,
            "parking": parking,
            "clubhouse": clubhouse,
            "facing_charges": facing_charges,
            "corpus_fund": corpus_fund,
            "gst_percent": gst_percent,
            "gst": gst,
            "gross_amount": gross,
        }

    @staticmethod
    def manual_cost_from_form(form, flat):
        sft = float(flat.get("sft", 0) or 0)
        rate = float(form.get("rate_per_sft") or 0)
        base_price = float(form.get("base_price") or (sft * rate))
        floor_rise = float(form.get("floor_rise") or 0)
        parking = float(form.get("parking") or 0)
        clubhouse = float(form.get("clubhouse") or 0)
        facing_charges = float(form.get("facing_charges") or 0)
        corpus_fund = float(form.get("corpus_fund") or 0)
        gst_percent = float(form.get("gst_percent") or 0)
        gst = float(form.get("gst") or ((base_price + floor_rise + parking + clubhouse + facing_charges) * gst_percent / 100))
        gross = float(form.get("gross_amount") or (base_price + floor_rise + parking + clubhouse + facing_charges + corpus_fund + gst))
        return {
            "rate_per_sft": rate,
            "base_price": base_price,
            "floor_rise": floor_rise,
            "parking": parking,
            "clubhouse": clubhouse,
            "facing_charges": facing_charges,
            "corpus_fund": corpus_fund,
            "gst_percent": gst_percent,
            "gst": gst,
            "gross_amount": gross,
        }

    @classmethod
    def book_flat(cls, customer_id, customer, flat, cost_sheet, mode="auto"):
        gross = float(cost_sheet.get("gross_amount", 0) or 0)
        booking = {
            "customer_id": customer_id,
            "customer_name": customer.get("name", ""),
            "flat_id": flat["_id"],
            "project_id": flat["project_id"],
            "tower_id": flat["tower_id"],
            "project": flat.get("project", ""),
            "flat_no": flat["flat_no"],
            "tower": flat["tower"],
            "floor": flat.get("floor"),
            "sft": flat.get("sft"),
            "facing": flat.get("facing"),
            "cost_mode": mode,
            "cost_sheet": cost_sheet,
            "rate_per_sft": float(cost_sheet.get("rate_per_sft", 0) or 0),
            "base_price": float(cost_sheet.get("base_price", 0) or 0),
            "floor_rise": float(cost_sheet.get("floor_rise", 0) or 0),
            "parking": float(cost_sheet.get("parking", 0) or 0),
            "clubhouse": float(cost_sheet.get("clubhouse", 0) or 0),
            "facing_charges": float(cost_sheet.get("facing_charges", 0) or 0),
            "corpus_fund": float(cost_sheet.get("corpus_fund", 0) or 0),
            "infrastructure_charges": float(cost_sheet.get("infrastructure_charges", 0) or 0),
            "other_charges": float(cost_sheet.get("other_charges", 0) or 0),
            "legal_documentation": float(cost_sheet.get("legal_documentation", 0) or 0),
            "maintenance_deposit": float(cost_sheet.get("maintenance_deposit", 0) or 0),
            "other_gst": float(cost_sheet.get("other_gst", 0) or 0),
            "gst_percent": float(cost_sheet.get("gst_percent", 0) or 0),
            "gst": float(cost_sheet.get("gst", 0) or 0),
            "gross_amount": gross,
            "paid_amount": 0,
            "due_amount": gross,
            "booked_at": datetime.utcnow(),
        }
        inserted = cls.create(booking)
        CustomerService.update(customer_id, {"project_id": flat["project_id"]})
        FlatService.link_booking(flat["_id"], customer_id, inserted)
        return inserted

    @classmethod
    def by_flat(cls, flat_id):
        return cls.collection().find_one(cls.scoped_query({"flat_id": str(flat_id)}))

    @classmethod
    def by_customer(cls, customer_id):
        return cls.collection().find_one(cls.scoped_query({"customer_id": str(customer_id)}))

    @classmethod
    def update_payment(cls, booking_id, amount, tds=0):
        booking = cls.get(booking_id)
        paid = float(booking.get("paid_amount", 0)) + float(amount or 0)
        due = max(float(booking.get("gross_amount", 0)) - paid, 0)
        total_tds = float(booking.get("tds", 0) or 0) + float(tds or 0)
        cls.collection().update_one(cls.scoped_query({"_id": ObjectId(booking_id)}), {"$set": {"paid_amount": paid, "due_amount": due, "tds": total_tds}})
