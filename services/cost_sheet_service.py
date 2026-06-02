from copy import deepcopy
from datetime import datetime

from bson import ObjectId

from services.base_service import BaseService


DEFAULT_PAYMENT_SCHEDULE = [
    {"stage": "Booking Advance", "percentage": 10.0},
    {"stage": "Within 60 Days", "percentage": 10.0},
    {"stage": "Foundation Completion", "percentage": 10.0},
    {"stage": "Plinth Completion", "percentage": 10.0},
    {"stage": "Slab Completion", "percentage": 10.0},
    {"stage": "Brick Work Completion", "percentage": 10.0},
    {"stage": "Plastering Completion", "percentage": 10.0},
    {"stage": "Flooring Completion", "percentage": 10.0},
    {"stage": "Painting Completion", "percentage": 10.0},
    {"stage": "Handover / Possession", "percentage": 10.0},
]

DEFAULT_NOTES = [
    "GST applicable as per prevailing rates.",
    "Registration charges shall be borne by the purchaser.",
    "Government taxes are subject to change.",
    "Any increase in statutory charges shall be extra.",
]


class CostSheetTemplateService(BaseService):
    collection_name = "cost_sheet_templates"

    @classmethod
    def defaults(cls):
        return {
            "key": "global",
            "base_price_per_sft": 0.0,
            "infrastructure_per_sft": 0.0,
            "car_parking": 0.0,
            "floor_rise_per_sft_per_floor": 0.0,
            "facing_charges_per_sft": 0.0,
            "clubhouse_per_sft": 0.0,
            "other_charges": 0.0,
            "legal_documentation": 0.0,
            "maintenance_deposit": 0.0,
            "corpus_fund_per_sft": 0.0,
            "sale_gst_percent": 5.0,
            "additional_gst_percent": 18.0,
            "notes": list(DEFAULT_NOTES),
            "terms_conditions": "I have read and understood the above terms and conditions and agree to the payment schedule.",
            "payment_schedule": deepcopy(DEFAULT_PAYMENT_SCHEDULE),
        }

    @classmethod
    def current(cls):
        template = cls.collection().find_one(cls.scoped_query({"key": "global"}))
        if not template:
            return cls.defaults()
        from utils.formatters import serialize_doc

        current = cls.defaults()
        current.update(serialize_doc(template))
        current["payment_schedule"] = current.get("payment_schedule") or deepcopy(DEFAULT_PAYMENT_SCHEDULE)
        current["notes"] = current.get("notes") or list(DEFAULT_NOTES)
        return current

    @staticmethod
    def _num(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _lines(value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [line.strip() for line in str(value or "").splitlines() if line.strip()]

    @classmethod
    def from_form(cls, form):
        milestones = []
        stages = form.getlist("stage[]")
        percentages = form.getlist("percentage[]")
        for stage, percentage in zip(stages, percentages):
            if stage.strip():
                milestones.append({"stage": stage.strip(), "percentage": cls._num(percentage)})
        return {
            "key": "global",
            "base_price_per_sft": cls._num(form.get("base_price_per_sft")),
            "infrastructure_per_sft": cls._num(form.get("infrastructure_per_sft")),
            "car_parking": cls._num(form.get("car_parking")),
            "floor_rise_per_sft_per_floor": cls._num(form.get("floor_rise_per_sft_per_floor")),
            "facing_charges_per_sft": cls._num(form.get("facing_charges_per_sft")),
            "clubhouse_per_sft": cls._num(form.get("clubhouse_per_sft")),
            "other_charges": cls._num(form.get("other_charges")),
            "legal_documentation": cls._num(form.get("legal_documentation")),
            "maintenance_deposit": cls._num(form.get("maintenance_deposit")),
            "corpus_fund_per_sft": cls._num(form.get("corpus_fund_per_sft")),
            "sale_gst_percent": cls._num(form.get("sale_gst_percent")),
            "additional_gst_percent": cls._num(form.get("additional_gst_percent")),
            "notes": cls._lines(form.get("notes")) or list(DEFAULT_NOTES),
            "terms_conditions": form.get("terms_conditions", "").strip() or cls.defaults()["terms_conditions"],
            "payment_schedule": milestones or deepcopy(DEFAULT_PAYMENT_SCHEDULE),
            "updated_at": datetime.utcnow(),
        }

    @classmethod
    def save(cls, data):
        cls.collection().update_one(cls.scoped_query({"key": "global"}), {"$set": data}, upsert=True)

    @classmethod
    def calculate_amounts(cls, flat, template=None):
        template = template or cls.current()
        sft = cls._num(flat.get("sft"))
        floor = cls._num(flat.get("floor"))
        base_rate = cls._num(template.get("base_price_per_sft"))
        infrastructure_rate = cls._num(template.get("infrastructure_per_sft"))
        floor_rise_rate = cls._num(template.get("floor_rise_per_sft_per_floor"))
        facing_rate = cls._num(template.get("facing_charges_per_sft"))
        clubhouse_rate = cls._num(template.get("clubhouse_per_sft"))
        corpus_rate = cls._num(template.get("corpus_fund_per_sft"))
        sale_gst_percent = cls._num(template.get("sale_gst_percent"))
        additional_gst_percent = cls._num(template.get("additional_gst_percent"))

        base_price = sft * base_rate
        infrastructure = sft * infrastructure_rate
        parking = cls._num(template.get("car_parking"))
        floor_rise = sft * floor * floor_rise_rate
        facing_charges = sft * facing_rate
        clubhouse = sft * clubhouse_rate
        sale_total = base_price + infrastructure + parking + floor_rise + facing_charges + clubhouse
        sale_gst = sale_total * sale_gst_percent / 100
        sale_sub_total = sale_total + sale_gst

        other_charges = cls._num(template.get("other_charges"))
        legal = cls._num(template.get("legal_documentation"))
        maintenance = cls._num(template.get("maintenance_deposit"))
        additional_total = other_charges + legal + maintenance
        additional_gst = additional_total * additional_gst_percent / 100
        additional_sub_total = additional_total + additional_gst

        corpus_fund = sft * corpus_rate
        grand_total = sale_sub_total + additional_sub_total + corpus_fund
        return {
            "rate_per_sft": base_rate,
            "base_price": base_price,
            "infrastructure_charges": infrastructure,
            "floor_rise": floor_rise,
            "parking": parking,
            "clubhouse": clubhouse,
            "facing_charges": facing_charges,
            "corpus_fund": corpus_fund,
            "gst_percent": sale_gst_percent,
            "gst": sale_gst,
            "gross_amount": grand_total,
            "other_charges": other_charges,
            "legal_documentation": legal,
            "maintenance_deposit": maintenance,
            "other_gst": additional_gst,
            "sale_total": sale_total,
            "sale_sub_total": sale_sub_total,
            "additional_total": additional_total,
            "additional_gst_percent": additional_gst_percent,
            "additional_sub_total": additional_sub_total,
            "grand_total": grand_total,
        }

    @classmethod
    def build_snapshot(cls, booking, customer=None, flat=None, project=None, tower=None, template=None):
        template = template or cls.current()
        flat = flat or booking
        project = project or {}
        tower = tower or {}
        amounts = cls.calculate_amounts(flat, template)
        schedule = []
        for item in template.get("payment_schedule") or DEFAULT_PAYMENT_SCHEDULE:
            percentage = cls._num(item.get("percentage"))
            total = amounts["grand_total"] * percentage / 100
            value = total / (1 + amounts["gst_percent"] / 100) if amounts["gst_percent"] else total
            gst = total - value
            schedule.append({
                "stage": item.get("stage", ""),
                "percentage": percentage,
                "value": value,
                "gst": gst,
                "total": total,
            })
        return {
            "generated_at": datetime.utcnow(),
            "template": deepcopy(template),
            "amounts": amounts,
            "notes": list(template.get("notes") or DEFAULT_NOTES),
            "terms_conditions": template.get("terms_conditions") or cls.defaults()["terms_conditions"],
            "payment_schedule": schedule,
            "customer": customer or {},
            "flat": flat or {},
            "project": project or {},
            "tower": tower or {},
            "booking": booking or {},
        }

    @classmethod
    def snapshot_for_booking(cls, booking, customer=None, flat=None, project=None, tower=None, regenerate=False):
        if booking.get("cost_sheet_snapshot") and not regenerate:
            return booking["cost_sheet_snapshot"]
        snapshot = cls.build_snapshot(booking, customer=customer, flat=flat, project=project, tower=tower)
        from services.customer_service import BookingService

        update = {"cost_sheet_snapshot": snapshot}
        update.update(snapshot["amounts"])
        BookingService.collection().update_one(BookingService.scoped_query({"_id": ObjectId(booking["_id"])}), {"$set": update})
        return snapshot
