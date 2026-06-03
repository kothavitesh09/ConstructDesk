from datetime import datetime

from flask import current_app
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import bcrypt
except ImportError:
    bcrypt = None

from database.mongo import get_db
from utils.formatters import serialize_doc, to_object_id


COMPANY_STATUSES = ("pending", "active", "suspended", "rejected")
ROLES = ("super_admin", "company_admin", "sales_manager", "accountant", "site_engineer", "viewer")


def password_hash(password):
    if bcrypt:
        return bcrypt.hashpw((password or "").encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return generate_password_hash(password or "")


def verify_password(stored_hash, password):
    if bcrypt and stored_hash and stored_hash.startswith("$2"):
        return bcrypt.checkpw((password or "").encode("utf-8"), stored_hash.encode("utf-8"))
    return check_password_hash(stored_hash or "", password or "")


class AuthService:
    @staticmethod
    def companies():
        return get_db().companies

    @staticmethod
    def users():
        return get_db().users

    @staticmethod
    def audit_logs():
        return get_db().audit_logs

    @classmethod
    def ensure_super_admin(cls):
        user_id = current_app.config["SUPER_ADMIN_USER_ID"].strip().lower()
        email = current_app.config["SUPER_ADMIN_EMAIL"].strip().lower()
        if not user_id:
            return None
        super_admin = cls.users().find_one({"role": "super_admin"})
        fixed_profile = {
            "name": current_app.config.get("SUPER_ADMIN_NAME", "Super Admin"),
            "user_id": user_id,
            "email": email,
            "password_hash": password_hash(current_app.config["SUPER_ADMIN_PASSWORD"]),
            "role": "super_admin",
            "status": "active",
            "updated_at": datetime.utcnow(),
        }
        if super_admin:
            cls.users().update_one({"_id": super_admin["_id"]}, {"$set": fixed_profile})
            return serialize_doc(cls.users().find_one({"_id": super_admin["_id"]}))
        existing = cls.users().find_one({"user_id": user_id, "role": "super_admin"})
        if existing:
            cls.users().update_one({"_id": existing["_id"]}, {"$set": fixed_profile})
            return serialize_doc(cls.users().find_one({"_id": existing["_id"]}))
        if email and cls.users().find_one({"email": email, "role": "super_admin"}):
            existing = cls.users().find_one({"email": email, "role": "super_admin"})
            cls.users().update_one({"_id": existing["_id"]}, {"$set": fixed_profile})
            return serialize_doc(cls.users().find_one({"_id": existing["_id"]}))
        result = cls.users().insert_one({
            **fixed_profile,
            "created_at": datetime.utcnow(),
        })
        return serialize_doc(cls.users().find_one({"_id": result.inserted_id}))

    @classmethod
    def register_company(cls, form):
        email = form.get("email", "").strip().lower()
        if cls.companies().find_one({"email": email}) or cls.users().find_one({"email": email}):
            raise ValueError("An account with this email already exists.")
        if form.get("password") != form.get("confirm_password"):
            raise ValueError("Passwords do not match.")

        now = datetime.utcnow()
        company = {
            "company_name": form.get("company_name", "").strip(),
            "owner_name": form.get("owner_name", "").strip(),
            "phone": form.get("phone", "").strip(),
            "email": email,
            "gst_number": form.get("gst_number", "").strip(),
            "address": form.get("address", "").strip(),
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }
        try:
            company_id = cls.companies().insert_one(company).inserted_id
        except DuplicateKeyError as exc:
            raise ValueError("An account with this email already exists.") from exc

        user = {
            "company_id": str(company_id),
            "name": company["owner_name"],
            "email": email,
            "password_hash": password_hash(form.get("password")),
            "role": "company_admin",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        try:
            cls.users().insert_one(user)
        except DuplicateKeyError as exc:
            cls.companies().delete_one({"_id": company_id})
            raise ValueError("An account with this email already exists.") from exc
        except Exception:
            cls.companies().delete_one({"_id": company_id})
            raise
        cls.log("company_registered", company_id=str(company_id), details={"email": email})
        return str(company_id)

    @classmethod
    def authenticate_company_user(cls, email, password):
        user = cls.users().find_one({"email": email.strip().lower(), "role": {"$ne": "super_admin"}})
        if not user or user.get("status") != "active" or not verify_password(user.get("password_hash"), password):
            return None, "Invalid email or password."
        company_oid = to_object_id(user.get("company_id"))
        company = cls.companies().find_one({"_id": company_oid}) if company_oid else None
        if not company:
            return None, "Company account was not found."
        if company.get("status") != "active":
            return None, f"Company account is {company.get('status', 'not active')}."
        return serialize_doc(user), None

    @classmethod
    def authenticate_super_admin(cls, user_id, password):
        cls.ensure_super_admin()
        login_id = user_id.strip().lower()
        user = cls.users().find_one({"user_id": login_id, "role": "super_admin"})
        if not user or user.get("status") != "active" or not verify_password(user.get("password_hash"), password):
            return None
        return serialize_doc(user)

    @classmethod
    def update_company_status(cls, company_id, status, actor_id=None):
        if status not in COMPANY_STATUSES:
            return False
        oid = to_object_id(company_id)
        if not oid:
            return False
        cls.companies().update_one({"_id": oid}, {"$set": {"status": status, "updated_at": datetime.utcnow()}})
        cls.log(f"company_{status}", company_id=company_id, actor_id=actor_id)
        return True

    @classmethod
    def platform_stats(cls):
        db = get_db()
        return {
            "total_companies": db.companies.count_documents({}),
            "pending_companies": db.companies.count_documents({"status": "pending"}),
            "active_companies": db.companies.count_documents({"status": "active"}),
            "suspended_companies": db.companies.count_documents({"status": "suspended"}),
            "total_projects": db.projects.count_documents({}),
            "total_users": db.users.count_documents({"role": {"$ne": "super_admin"}}),
        }

    @classmethod
    def log(cls, action, company_id=None, actor_id=None, details=None):
        cls.audit_logs().insert_one({
            "action": action,
            "company_id": company_id,
            "actor_id": actor_id,
            "details": details or {},
            "created_at": datetime.utcnow(),
        })
