from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from services.company_service import ACCOUNT_PURPOSES, CompanyService
from services.cost_sheet_service import CostSheetTemplateService
from services.project_service import FlatService, ProjectService, TowerService

masters_bp = Blueprint("masters", __name__)


def save_company_upload(file_storage, prefix):
    if not file_storage or not file_storage.filename:
        return None
    upload_dir = Path(current_app.root_path) / "static" / "uploads" / "company"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file_storage.filename)
    suffix = Path(filename).suffix
    stored_name = f"{prefix}-{uuid4().hex}{suffix}"
    file_storage.save(upload_dir / stored_name)
    return f"uploads/company/{stored_name}"


@masters_bp.route("/")
def workspace():
    projects = ProjectService.all({}, [("name", 1)])
    towers = TowerService.all({}, [("name", 1)])
    return render_template("masters.html", title="Masters", projects=projects, towers=towers)


@masters_bp.route("/cost-sheet", methods=["GET", "POST"])
def cost_sheet_master():
    if request.method == "POST":
        CostSheetTemplateService.save(CostSheetTemplateService.from_form(request.form))
        flash("Cost Sheet master template saved.", "success")
        return redirect(url_for("masters.cost_sheet_master"))
    template = CostSheetTemplateService.current()
    return render_template("cost_sheet_master.html", title="Cost Sheet Master", template=template)


@masters_bp.route("/company-details", methods=["GET", "POST"])
def company_details():
    company = CompanyService.current()
    active_tab = request.args.get("tab", "general")
    if request.method == "POST":
        section = request.form.get("section", "general")
        active_tab = section
        if section == "general":
            general = dict(company.get("general", {}))
            general.update({
                "company_name": request.form.get("company_name", "").strip(),
                "pan_number": request.form.get("pan_number", "").strip(),
                "gst_number": request.form.get("gst_number", "").strip(),
                "email": request.form.get("email", "").strip(),
                "mobile": request.form.get("mobile", "").strip(),
                "website": request.form.get("website", "").strip(),
            })
            logo_path = save_company_upload(request.files.get("logo"), "logo")
            if logo_path:
                general["logo_path"] = logo_path
            CompanyService.save_section("general", general)
            flash("Company information saved.", "success")
        elif section == "addresses":
            addresses = {}
            for key in ("registered", "corporate", "project_site"):
                addresses[key] = {
                    "line1": request.form.get(f"{key}_line1", "").strip(),
                    "line2": request.form.get(f"{key}_line2", "").strip(),
                    "city": request.form.get(f"{key}_city", "").strip(),
                    "state": request.form.get(f"{key}_state", "").strip(),
                    "pin": request.form.get(f"{key}_pin", "").strip(),
                }
            CompanyService.save_section("addresses", addresses)
            flash("Company addresses saved.", "success")
        elif section == "report_settings":
            settings = dict(company.get("report_settings", {}))
            settings.update({
                "authorized_signatory": request.form.get("authorized_signatory", "").strip(),
                "designation": request.form.get("designation", "").strip(),
                "footer_notes": request.form.get("footer_notes", "").strip(),
                "terms_conditions": request.form.get("terms_conditions", "").strip(),
            })
            signature_path = save_company_upload(request.files.get("signature"), "signature")
            if signature_path:
                settings["signature_path"] = signature_path
            CompanyService.save_section("report_settings", settings)
            flash("Report settings saved.", "success")
        return redirect(url_for("masters.company_details", tab=active_tab))
    return render_template("company_details.html", title="Company Details", company=company, account_purposes=ACCOUNT_PURPOSES, active_tab=active_tab)


@masters_bp.route("/company-details/bank-account", methods=["POST"])
def save_bank_account():
    accounts = CompanyService.bank_accounts()
    account_id = request.form.get("account_id") or uuid4().hex
    account = {
        "id": account_id,
        "purpose": request.form.get("purpose", "").strip(),
        "account_name": request.form.get("account_name", "").strip(),
        "account_number": request.form.get("account_number", "").strip(),
        "ifsc": request.form.get("ifsc", "").strip(),
        "bank_name": request.form.get("bank_name", "").strip(),
        "branch_name": request.form.get("branch_name", "").strip(),
    }
    accounts = [item for item in accounts if item.get("id") != account_id]
    accounts.append(account)
    CompanyService.save_bank_accounts(accounts)
    flash("Bank account saved.", "success")
    return redirect(url_for("masters.company_details", tab="bank_accounts"))


@masters_bp.route("/company-details/bank-account/<account_id>/delete", methods=["POST"])
def delete_bank_account(account_id):
    accounts = [item for item in CompanyService.bank_accounts() if item.get("id") != account_id]
    CompanyService.save_bank_accounts(accounts)
    flash("Bank account deleted.", "success")
    return redirect(url_for("masters.company_details", tab="bank_accounts"))


@masters_bp.route("/projects", methods=["GET", "POST"])
def projects():
    if request.method == "POST":
        project_id = ProjectService.create({
            "name": request.form["name"].strip(),
            "area": request.form.get("area"),
            "acres": float(request.form.get("acres") or 0),
            "guntas": float(request.form.get("guntas") or 0),
            "construct_area": request.form.get("construct_area"),
            "built_up_area": request.form.get("built_up_area"),
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date"),
            "duration": request.form.get("duration"),
        })
        session["current_project_id"] = project_id
        project = ProjectService.get(project_id)
        tower_names = request.form.getlist("tower_name[]")
        tower_floors = request.form.getlist("tower_floors[]")
        flat_nos = request.form.getlist("flat_no[]")
        sfts = request.form.getlist("sft[]")
        facings = request.form.getlist("facing[]")
        pattern_rows = []
        for flat_no, sft, facing in zip(flat_nos, sfts, facings):
            if flat_no and sft and facing:
                pattern_rows.append({"flat_no": flat_no, "sft": sft, "facing": facing, "project": project["name"]})
        generated_count = 0
        for tower_name, floors in zip(tower_names, tower_floors):
            if tower_name and floors:
                tower_id = TowerService.create({
                    "project_id": project_id,
                    "project": project["name"],
                    "name": tower_name.strip().upper(),
                    "floors": int(floors or 0),
                })
                if pattern_rows:
                    generated_count += len(FlatService.generate_inventory(project_id, tower_id, tower_name.strip().upper(), int(floors or 0), pattern_rows))
        flash(f"Project created successfully. {generated_count} flats generated.", "success")
        return redirect(url_for("masters.workspace"))
    return render_template("project_form.html", title="Create Project")


@masters_bp.route("/towers", methods=["GET", "POST"])
def towers():
    projects = ProjectService.all({}, [("name", 1)])
    if request.method == "POST":
        project = ProjectService.get(request.form["project_id"])
        TowerService.create({
            "project_id": project["_id"],
            "project": project["name"],
            "name": request.form["name"].strip().upper(),
            "floors": int(request.form.get("floors") or 0),
        })
        flash("Tower setup saved.", "success")
        return redirect(url_for("masters.workspace"))
    return render_template("tower_form.html", title="Towers Setup", projects=projects)


@masters_bp.route("/inventory-generator", methods=["GET", "POST"])
def inventory_generator():
    projects = ProjectService.all({}, [("name", 1)])
    towers = TowerService.all({}, [("name", 1)])
    generated_count = None
    if request.method == "POST":
        tower = TowerService.get(request.form["tower_id"])
        project = ProjectService.get(tower["project_id"])
        rows = []
        flat_nos = request.form.getlist("flat_no[]")
        sfts = request.form.getlist("sft[]")
        facings = request.form.getlist("facing[]")
        for flat_no, sft, facing in zip(flat_nos, sfts, facings):
            if flat_no and sft and facing:
                rows.append({"flat_no": flat_no, "sft": sft, "facing": facing, "project": project["name"]})
        generated = FlatService.generate_inventory(project["_id"], tower["_id"], tower["name"], tower["floors"], rows)
        generated_count = len(generated)
        flash(f"{generated_count} flats generated.", "success")
    return render_template("inventory_generator.html", title="Inventory Generator", projects=projects, towers=towers, generated_count=generated_count)
