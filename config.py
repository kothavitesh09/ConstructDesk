import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "construction-erp-dev-key")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "construction_erp")
    COMPANY_NAME = os.getenv("COMPANY_NAME", "ConstructDesk ERP")
    DEFAULT_PROJECT = os.getenv("DEFAULT_PROJECT", "")
    SUPER_ADMIN_NAME = os.getenv("SUPER_ADMIN_NAME", "Super Admin")
    SUPER_ADMIN_USER_ID = os.getenv("SUPER_ADMIN_USER_ID", "kothavitesh")
    SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "kothavitesh@builddesk.local")
    SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD", "Rkvc@2005")
