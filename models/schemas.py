from datetime import datetime


def timestamped(data):
    now = datetime.utcnow()
    data.setdefault("created_at", now)
    data["updated_at"] = now
    return data


FLAT_STATUSES = ("Available", "Sold", "Mortgage")
PAYMENT_MODES = ("Cash", "Cheque", "NEFT", "RTGS", "UPI", "Card")
