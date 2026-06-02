from flask import Blueprint, jsonify, request

from services.cost_sheet_service import CostSheetTemplateService
from services.customer_service import BookingService, CustomerService
from services.finance_service import ReceiptService
from services.project_service import FlatService, ProjectService
from utils.auth import current_project_id

api_bp = Blueprint("api", __name__)


@api_bp.route("/global-search")
def global_search():
    term = request.args.get("q", "").strip()
    if len(term) < 2:
        return jsonify([])
    scoped = {"project_id": current_project_id()} if current_project_id() else {}
    flats = FlatService.all({**scoped, "flat_no": {"$regex": term, "$options": "i"}}, [("flat_no", 1)], 5)
    customers = CustomerService.search(term, 5)
    receipts = ReceiptService.all({**scoped, "receipt_no": {"$regex": term, "$options": "i"}}, [("created_at", -1)], 5)
    results = []
    results += [{"type": "Flat", "label": f["flat_no"], "url": f"/inventory/flat/{f['_id']}"} for f in flats]
    results += [{"type": "Customer", "label": c["name"], "url": f"/customers/profile/{c['_id']}"} for c in customers]
    results += [{"type": "Receipt", "label": r.get("receipt_no", "Receipt"), "url": f"/receipts?booking_id={r.get('booking_id', '')}"} for r in receipts]
    return jsonify(results[:10])


@api_bp.route("/project/<project_id>/costing")
def project_costing(project_id):
    project = ProjectService.get(project_id)
    return jsonify(project.get("costing", {}) if project else {})


@api_bp.route("/flat/<flat_id>/cost-preview")
def flat_cost_preview(flat_id):
    flat = FlatService.get(flat_id)
    if not flat:
        return jsonify({})
    return jsonify(CostSheetTemplateService.calculate_amounts(flat))
