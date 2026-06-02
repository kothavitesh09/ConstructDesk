from flask import Flask, abort, g, redirect, request, session, url_for

from config import Config
from database.mongo import close_client, get_db, init_indexes
from routes.auth import auth_bp, super_admin_bp
from routes.dashboard import dashboard_bp
from routes.masters import masters_bp
from routes.inventory import inventory_bp
from routes.customers import customers_bp
from routes.finance import finance_bp
from routes.receipts import receipts_bp
from routes.api import api_bp
from services.auth_service import AuthService
from services.project_service import ProjectService
from utils.auth import PUBLIC_ENDPOINTS, can_access
from utils.formatters import serialize_doc, to_object_id


MODULE_BY_BLUEPRINT = {
    "dashboard": "dashboard",
    "masters": "masters",
    "inventory": "inventory",
    "customers": "customers",
    "finance": "finance",
    "receipts": "receipts",
    "api": "dashboard",
}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp)
    app.register_blueprint(super_admin_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(masters_bp, url_prefix="/masters")
    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(finance_bp, url_prefix="/finance")
    app.register_blueprint(receipts_bp, url_prefix="/receipts")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.before_request
    def load_user_and_authorize():
        g.current_user = None
        g.current_company = None
        if request.endpoint in PUBLIC_ENDPOINTS or (request.endpoint or "").startswith("static"):
            return None

        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("auth.landing"))

        user_oid = to_object_id(user_id)
        if not user_oid:
            session.clear()
            return redirect(url_for("auth.landing"))
        user = get_db().users.find_one({"_id": user_oid})
        if not user or user.get("status") != "active":
            session.clear()
            return redirect(url_for("auth.landing"))
        g.current_user = serialize_doc(user)

        if user.get("role") == "super_admin":
            if request.blueprint not in {"super_admin", "auth"}:
                return redirect(url_for("super_admin.dashboard"))
            return None

        company_oid = to_object_id(user.get("company_id"))
        company = get_db().companies.find_one({"_id": company_oid}) if company_oid else None
        if not company or company.get("status") != "active":
            session.clear()
            return redirect(url_for("auth.company_login"))
        g.current_company = serialize_doc(company)
        if not session.get("current_project_id"):
            project = get_db().projects.find_one({"company_id": user["company_id"]}, sort=[("created_at", 1)])
            if project:
                session["current_project_id"] = str(project["_id"])

        module = MODULE_BY_BLUEPRINT.get(request.blueprint)
        if module and not can_access(module):
            abort(403)
        return None

    @app.context_processor
    def inject_auth_context():
        projects = []
        active_project = None
        if getattr(g, "current_user", None) and g.current_user.get("role") != "super_admin":
            projects = ProjectService.all({}, [("name", 1)])
            active_project = next((project for project in projects if project["_id"] == session.get("current_project_id")), None)
        return {
            "current_user": getattr(g, "current_user", None),
            "current_company": getattr(g, "current_company", None),
            "tenant_projects": projects,
            "active_project": active_project,
        }

    app.teardown_appcontext(close_client)
    init_indexes(app)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
