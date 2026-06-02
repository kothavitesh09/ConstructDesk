from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database.mongo import get_db
from services.auth_service import AuthService
from services.project_service import ProjectService
from utils.auth import roles_required
from utils.formatters import serialize_doc, to_object_id

auth_bp = Blueprint("auth", __name__)


def _first_project_id():
    project = ProjectService.collection().find_one({"company_id": session.get("company_id")}, sort=[("created_at", 1)])
    return str(project["_id"]) if project else None


def _sign_in(user):
    session.clear()
    session["user_id"] = user["_id"]
    session["role"] = user["role"]
    if user.get("company_id"):
        session["company_id"] = user["company_id"]
        session["current_project_id"] = _first_project_id()


@auth_bp.route("/login")
def landing():
    if session.get("user_id"):
        return redirect(url_for("super_admin.dashboard") if session.get("role") == "super_admin" else url_for("dashboard.index"))
    return redirect(url_for("auth.company_login"))


@auth_bp.route("/company/sign-in", methods=["GET", "POST"])
def company_login():
    if request.method == "POST":
        user, error = AuthService.authenticate_company_user(request.form.get("email", ""), request.form.get("password", ""))
        if user:
            _sign_in(user)
            return redirect(url_for("dashboard.index"))
        flash(error or "Invalid email or password.", "danger")
    return render_template("company_login.html", title="Company Sign In")


@auth_bp.route("/company/register", methods=["GET", "POST"])
def register_company():
    if request.method == "POST":
        try:
            AuthService.register_company(request.form)
        except ValueError as exc:
            flash(str(exc), "danger")
        else:
            return redirect(url_for("auth.registration_success"))
    return render_template("company_register.html", title="Create Company Account")


@auth_bp.route("/company/registration-success")
def registration_success():
    return render_template("registration_success.html", title="Registration Submitted")


@auth_bp.route("/super-admin/sign-in", methods=["GET", "POST"])
def super_admin_login():
    if request.method == "POST":
        user = AuthService.authenticate_super_admin(request.form.get("user_id", ""), request.form.get("password", ""))
        if user:
            _sign_in(user)
            return redirect(url_for("super_admin.dashboard"))
        flash("Invalid Super Admin user ID or password.", "danger")
    return render_template("super_admin_login.html", title="Super Admin Sign In")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.landing"))


@auth_bp.post("/project/switch")
def switch_project():
    project_id = request.form.get("project_id")
    if session.get("role") == "super_admin":
        return redirect(url_for("super_admin.dashboard"))
    project_oid = to_object_id(project_id)
    project = get_db().projects.find_one({"_id": project_oid, "company_id": session.get("company_id")}) if project_oid else None
    if project:
        session["current_project_id"] = str(project["_id"])
    return redirect(request.referrer or url_for("dashboard.index"))


super_admin_bp = Blueprint("super_admin", __name__, url_prefix="/super-admin")


@super_admin_bp.route("/")
@roles_required("super_admin")
def dashboard():
    companies = [serialize_doc(company) for company in AuthService.companies().find({}).sort("created_at", -1)]
    return render_template("super_admin_dashboard.html", title="Super Admin", companies=companies, stats=AuthService.platform_stats())


@super_admin_bp.post("/companies/<company_id>/<status>")
@roles_required("super_admin")
def update_company_status(company_id, status):
    if AuthService.update_company_status(company_id, status, actor_id=session.get("user_id")):
        flash(f"Company marked as {status}.", "success")
    else:
        flash("Invalid company status.", "danger")
    return redirect(url_for("super_admin.dashboard"))
