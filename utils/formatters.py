from bson import ObjectId


def to_object_id(value):
    if not value:
        return None
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except Exception:
        return None


def serialize_doc(doc):
    if not doc:
        return doc
    converted = dict(doc)
    converted["_id"] = str(converted["_id"])
    return converted


def money(value):
    try:
        return f"{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def number(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
