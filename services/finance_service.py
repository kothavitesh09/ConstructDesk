from datetime import datetime

from services.base_service import BaseService
from services.customer_service import BookingService
from utils.auth import current_project_id


class ReceiptService(BaseService):
    collection_name = "receipts"
    project_scoped = True

    @classmethod
    def next_receipt_no(cls):
        count = cls.collection().count_documents(cls.scoped_query({}))
        return f"REC-{datetime.utcnow().year}-{count + 1:05d}"

    @classmethod
    def create_receipt(cls, data):
        data["receipt_no"] = data.get("receipt_no") or cls.next_receipt_no()
        amount = float(data.get("amount", 0) or 0)
        receipt_id = cls.create(data)
        if data.get("booking_id"):
            BookingService.update_payment(data["booking_id"], amount, data.get("tds", 0))
        return receipt_id

    @classmethod
    def update_receipt(cls, receipt_id, data):
        current = cls.get(receipt_id)
        if not current:
            return False
        old_amount = float(current.get("amount", 0) or 0)
        old_tds = float(current.get("tds", 0) or 0)
        new_amount = float(data.get("amount", old_amount) or 0)
        new_tds = float(data.get("tds", old_tds) or 0)
        data["amount"] = new_amount
        data["tds"] = new_tds
        updated = cls.update(receipt_id, data)
        if updated and current.get("booking_id"):
            BookingService.update_payment(current["booking_id"], new_amount - old_amount, new_tds - old_tds)
        return updated

    @classmethod
    def update_status(cls, receipt_id, status):
        if status not in {"Pending", "Cleared", "Bounced"}:
            return False
        return cls.update(receipt_id, {"receipt_status": status})

    @classmethod
    def recent(cls, limit=25):
        query = {"project_id": current_project_id()} if current_project_id() else {}
        return cls.all(query, [("created_at", -1)], limit)


class ReportService:
    @staticmethod
    def dashboard(db):
        from services.base_service import BaseService

        query = BaseService.scoped_query({})
        total = db.flats.count_documents(query)
        sold = db.flats.count_documents({**query, "status": "Sold"})
        mortgage = db.flats.count_documents({**query, "status": "Mortgage"})
        receipts = list(db.receipts.find(query))
        bookings = list(db.bookings.find(query))
        total_collections = sum(float(r.get("amount", 0) or 0) for r in receipts)
        pending_due = sum(float(b.get("due_amount", 0) or 0) for b in bookings)
        return {
            "total_flats": total,
            "sold_flats": sold,
            "available_flats": db.flats.count_documents({**query, "status": "Available"}),
            "mortgage_flats": mortgage,
            "total_collections": total_collections,
            "pending_due": pending_due,
        }
