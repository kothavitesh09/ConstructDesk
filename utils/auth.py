from functools import wraps

from flask import abort, g, has_request_context, redirect, request, session, url_for


PUBLIC_ENDPOINTS = {
    "auth.landing",
    "auth.company_login",
    "auth.register_company",
    "auth.registration_success",
    "auth.super_admin_login",
    "static",
}

ROLE_PERMISSIONS = {
    "super_admin": {"platform"},
    "company_admin": {"all"},
    "sales_manager": {"dashboard", "customers"},
    "accountant": {"dashboard", "finance", "receipts"},
    "site_engineer": {"dashboard", "masters", "inventory"},
    "viewer": {"dashboard", "masters", "inventory", "customers", "finance", "receipts"},
}


def current_user():
    return getattr(g, "current_user", None)


def current_company_id():
    user = current_user()
    return user.get("company_id") if user and user.get("role") != "super_admin" else None


def current_project_id():
    if not has_request_context():
        return None
    return session.get("current_project_id")


def is_super_admin():
    user = current_user()
    return bool(user and user.get("role") == "super_admin")


def can_access(module):
    user = current_user()
    if not user:
        return False
    permissions = ROLE_PERMISSIONS.get(user.get("role"), set())
    return "all" in permissions or module in permissions


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("auth.landing", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("auth.landing"))
            if user.get("role") not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
