from threading import Lock

from flask import current_app
from pymongo import MongoClient
from pymongo.errors import PyMongoError


_mongo_client = None
_mongo_client_lock = Lock()


def get_client():
    global _mongo_client
    if _mongo_client is None:
        with _mongo_client_lock:
            if _mongo_client is None:
                _mongo_client = MongoClient(current_app.config["MONGO_URI"], serverSelectionTimeoutMS=1200)
    return _mongo_client


def get_db():
    return get_client()[current_app.config["MONGO_DB_NAME"]]


def _key_list(keys):
    if isinstance(keys, str):
        return [(keys, 1)]
    return list(keys)


def _ensure_index(collection, keys, app, **options):
    keys = _key_list(keys)
    desired_unique = bool(options.get("unique"))
    desired_name = options.get("name")

    for index_name, spec in collection.index_information().items():
        if list(spec.get("key", [])) != keys:
            continue
        same_unique = bool(spec.get("unique")) == desired_unique
        same_name = not desired_name or index_name == desired_name
        if same_unique and same_name:
            return
        try:
            collection.drop_index(index_name)
        except PyMongoError as exc:
            app.logger.warning("Could not replace index %s on %s: %s", index_name, collection.name, exc)
            return
        break

    try:
        collection.create_index(keys, **options)
    except PyMongoError as exc:
        app.logger.warning("Could not create index on %s for %s: %s", collection.name, keys, exc)
        if desired_unique:
            fallback = dict(options)
            fallback.pop("unique", None)
            fallback["name"] = f"{options.get('name', collection.name + '_idx')}_nonunique_fallback"
            try:
                collection.create_index(keys, **fallback)
            except PyMongoError as fallback_exc:
                app.logger.warning("Could not create fallback index on %s for %s: %s", collection.name, keys, fallback_exc)


def _drop_index_if_present(collection, index_name, app):
    if index_name not in collection.index_information():
        return
    try:
        collection.drop_index(index_name)
    except PyMongoError as exc:
        app.logger.warning("Could not drop stale index %s on %s: %s", index_name, collection.name, exc)


def init_indexes(app):
    with app.app_context():
        db = get_db()

        _drop_index_if_present(db.companies, "companyId_1", app)

        _ensure_index(
            db.companies,
            "email",
            app,
            unique=True,
            name="uniq_companies_email"
        )
        _ensure_index(
            db.companies,
            "status",
            app,
            name="idx_companies_status"
        )

        _ensure_index(
            db.users,
            "email",
            app,
            unique=True,
            name="uniq_users_email"
        )
        _ensure_index(
            db.users,
            [("company_id", 1), ("role", 1)],
            app,
            name="idx_users_company_role"
        )

        _ensure_index(
            db.audit_logs,
            [("company_id", 1), ("created_at", -1)],
            app,
            name="idx_audit_logs_company_created"
        )

        _ensure_index(
            db.company_details,
            [("company_id", 1), ("key", 1)],
            app,
            unique=True,
            name="uniq_company_details_company_key"
        )

        _ensure_index(
            db.cost_sheet_templates,
            [("company_id", 1), ("key", 1)],
            app,
            unique=True,
            name="uniq_cost_sheet_templates_company_key"
        )

        _ensure_index(
            db.projects,
            [("company_id", 1), ("name", 1)],
            app,
            unique=True,
            name="uniq_projects_company_name"
        )

        _ensure_index(
            db.towers,
            [("company_id", 1), ("project_id", 1), ("name", 1)],
            app,
            unique=True,
            name="uniq_towers_company_project_name"
        )

        _ensure_index(
            db.flats,
            [("company_id", 1), ("project_id", 1), ("tower_id", 1), ("flat_no", 1)],
            app,
            unique=True,
            name="uniq_flats_company_project_tower_flat"
        )

        # Customers
        _ensure_index(
            db.customers,
            [("company_id", 1), ("project_id", 1)],
            app,
            name="idx_customers_company_project"
        )

        _ensure_index(
            db.customers,
            [("company_id", 1), ("project_id", 1), ("phone", 1)],
            app,
            name="idx_customers_phone"
        )

        _ensure_index(
            db.customers,
            [("company_id", 1), ("project_id", 1), ("aadhaar", 1)],
            app,
            name="idx_customers_aadhaar"
        )

        _ensure_index(
            db.customers,
            [("company_id", 1), ("project_id", 1), ("pan", 1)],
            app,
            name="idx_customers_pan"
        )

        _ensure_index(
            db.bookings,
            [("company_id", 1), ("project_id", 1)],
            app,
            name="idx_bookings_company_project"
        )

        _ensure_index(
            db.bookings,
            [("company_id", 1), ("customer_id", 1), ("flat_id", 1)],
            app,
            name="idx_bookings_company_customer_flat"
        )

        _ensure_index(
            db.receipts,
            [("company_id", 1), ("project_id", 1)],
            app,
            name="idx_receipts_company_project"
        )

        _ensure_index(
            db.receipts,
            [("company_id", 1), ("receipt_no", 1)],
            app,
            unique=True,
            name="uniq_receipts_company_receipt_no"
        )

        _ensure_index(
            db.receipts,
            [("company_id", 1), ("customer_id", 1), ("flat_id", 1), ("receipt_no", 1)],
            app,
            name="idx_receipts_company_customer_flat_receipt"
        )
