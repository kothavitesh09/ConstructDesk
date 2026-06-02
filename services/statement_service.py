from services.company_service import CompanyService
from services.customer_service import BookingService, CustomerService
from services.finance_service import ReceiptService
from services.project_service import FlatService


class CustomerStatementService:
    @staticmethod
    def build(booking_id):
        booking = BookingService.get(booking_id)
        if not booking:
            return None
        customer = CustomerService.get(booking.get("customer_id"))
        flat = FlatService.get(booking.get("flat_id"))
        receipts = ReceiptService.all({"booking_id": booking_id}, [("date", 1), ("receipt_no", 1)])
        total_collection = sum(float(r.get("amount", 0) or 0) for r in receipts)
        tds = float(booking.get("tds", 0) or 0)
        gross = float(booking.get("gross_amount", 0) or 0)
        gross_due = max(gross - total_collection, 0)
        other_charges = {
            "corpus_fund": float(booking.get("corpus_fund", 0) or 0),
            "legal_documentation": float(booking.get("legal_documentation", 0) or 0),
            "maintenance_deposit": float(booking.get("maintenance_deposit", 0) or 0),
            "gst_if_applicable": float(booking.get("other_gst", 0) or 0),
        }
        other_charges["sub_total"] = sum(other_charges.values())
        return {
            "booking": booking,
            "customer": customer or {},
            "flat": flat or {},
            "receipts": receipts,
            "company": CompanyService.current(),
            "cost": {
                "base_price": float(booking.get("base_price", 0) or 0),
                "infrastructure": float(booking.get("infrastructure_charges", 0) or 0),
                "floor_rise": float(booking.get("floor_rise", 0) or 0),
                "facing_charges": float(booking.get("facing_charges", 0) or 0),
                "clubhouse": float(booking.get("clubhouse", 0) or 0),
                "parking": float(booking.get("parking", 0) or 0),
                "gst": float(booking.get("gst", 0) or 0),
                "grand_total": gross,
                "sale_consideration": gross,
            },
            "summary": {
                "sale_receivable": gross,
                "collection_till_date": total_collection,
                "gross_due": gross_due,
                "tds": tds,
                "net_due": max(gross_due - tds, 0),
            },
            "other_charges": other_charges,
        }
