from flask import Blueprint, flash, redirect, render_template, request, url_for

from services.cost_sheet_service import CostSheetTemplateService
from services.customer_service import BookingService, CustomerService
from services.project_service import FlatService, ProjectService
from utils.auth import current_project_id

customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/")
def index():
    term = request.args.get("q", "")
    customers = CustomerService.search(term)
    return render_template("customers.html", title="Customers", customers=customers, q=term)


@customers_bp.route("/new", methods=["GET", "POST"])
def new():
    flat_query = {"status": "Available"}
    if current_project_id():
        flat_query["project_id"] = current_project_id()
    available_flats = FlatService.all(flat_query, [("tower", 1), ("floor", 1), ("flat_no", 1)])
    projects = ProjectService.all({}, [("name", 1)])
    if request.method == "POST":
        customer = {
            "name": request.form["name"].strip(),
            "phone": request.form.get("phone"),
            "email": request.form.get("email"),
            "aadhaar": request.form.get("aadhaar"),
            "pan": request.form.get("pan"),
            "address": request.form.get("address"),
        }
        customer_id = CustomerService.create(customer)
        flat = FlatService.get(request.form["flat_id"])
        if flat:
            project = ProjectService.get(flat["project_id"])
            mode = request.form.get("cost_mode", "auto")
            cost_sheet = CostSheetTemplateService.calculate_amounts(flat) if mode == "auto" else BookingService.manual_cost_from_form(request.form, flat)
            booking_id = BookingService.book_flat(customer_id, customer, flat, cost_sheet, mode)
            booking = BookingService.get(booking_id)
            CostSheetTemplateService.snapshot_for_booking(booking, customer=customer, flat=flat, project=project)
            flash("Customer booked and flat marked as sold.", "success")
            return redirect(url_for("inventory.flat_profile", flat_id=flat["_id"]))
        return redirect(url_for("customers.index"))
    return render_template("customer_form.html", title="New Customer", flats=available_flats, projects=projects)


@customers_bp.route("/profile/<customer_id>")
def profile(customer_id):
    booking = BookingService.by_customer(customer_id)
    if booking:
        return redirect(url_for("inventory.flat_profile", flat_id=booking["flat_id"]))
    customer = CustomerService.get(customer_id)
    return redirect(url_for("customers.index", q=customer.get("name", "") if customer else ""))


@customers_bp.route("/profile/<customer_id>/statement")
def statement(customer_id):
    booking = BookingService.by_customer(customer_id)
    if booking:
        return redirect(url_for("finance.customer_statement", booking_id=str(booking["_id"])))
    customer = CustomerService.get(customer_id)
    return redirect(url_for("customers.index", q=customer.get("name", "") if customer else ""))
