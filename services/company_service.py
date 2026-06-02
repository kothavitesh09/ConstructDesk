from services.base_service import BaseService
from utils.auth import current_company_id


ACCOUNT_PURPOSES = (
    "Collection Account",
    "Registration Account",
    "Corpus Fund Account",
    "Maintenance Deposit Account",
)


class CompanyService(BaseService):
    collection_name = "company_details"

    @classmethod
    def current(cls):
        query = cls.scoped_query({"key": "company"})
        company = cls.collection().find_one(query)
        if company:
            from utils.formatters import serialize_doc

            company = serialize_doc(company)
            company.setdefault("general", {})
            company.setdefault("addresses", {})
            company.setdefault("bank_accounts", [])
            company.setdefault("report_settings", {})
            return company
        return {
            "key": "company",
            "general": {},
            "addresses": {},
            "bank_accounts": [],
            "report_settings": {},
        }

    @classmethod
    def save_section(cls, section, data):
        query = cls.scoped_query({"key": "company"})
        update = {section: data}
        company_id = current_company_id()
        if company_id:
            update["company_id"] = company_id
        cls.collection().update_one(
            query,
            {"$set": update},
            upsert=True,
        )

    @classmethod
    def bank_accounts(cls):
        return cls.current().get("bank_accounts", [])

    @classmethod
    def save_bank_accounts(cls, accounts):
        cls.save_section("bank_accounts", accounts)

    @classmethod
    def display_name(cls, fallback="ConstructDesk ERP"):
        return cls.current().get("general", {}).get("company_name") or fallback
