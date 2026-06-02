from flask import has_request_context

from database.mongo import get_db
from models.schemas import timestamped
from utils.auth import current_company_id, current_project_id, is_super_admin
from utils.formatters import serialize_doc, to_object_id


class BaseService:
    collection_name = ""
    tenant_scoped = True
    project_scoped = False

    @classmethod
    def scoped_query(cls, query=None):
        query = dict(query or {})
        if not cls.tenant_scoped or not has_request_context() or is_super_admin():
            return query
        company_id = current_company_id()
        if company_id and "company_id" not in query:
            query["company_id"] = company_id
        project_id = current_project_id()
        if cls.project_scoped and project_id and "project_id" not in query:
            query["project_id"] = project_id
        return query

    @classmethod
    def collection(cls):
        return get_db()[cls.collection_name]

    @classmethod
    def all(cls, query=None, sort=None, limit=0):
        cursor = cls.collection().find(cls.scoped_query(query))
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return [serialize_doc(doc) for doc in cursor]

    @classmethod
    def get(cls, doc_id):
        oid = to_object_id(doc_id)
        return serialize_doc(cls.collection().find_one(cls.scoped_query({"_id": oid}))) if oid else None

    @classmethod
    def create(cls, data):
        if cls.tenant_scoped and has_request_context() and not is_super_admin():
            company_id = current_company_id()
            if company_id:
                data = dict(data)
                data.setdefault("company_id", company_id)
            project_id = current_project_id()
            if cls.project_scoped and project_id:
                data.setdefault("project_id", project_id)
        result = cls.collection().insert_one(timestamped(data))
        return str(result.inserted_id)

    @classmethod
    def update(cls, doc_id, data):
        oid = to_object_id(doc_id)
        if not oid:
            return False
        cls.collection().update_one(cls.scoped_query({"_id": oid}), {"$set": timestamped(data)})
        return True
