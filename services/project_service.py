from bson import ObjectId

from services.base_service import BaseService


class ProjectService(BaseService):
    collection_name = "projects"


class TowerService(BaseService):
    collection_name = "towers"
    project_scoped = True

    @classmethod
    def by_project(cls, project_id):
        return cls.all({"project_id": str(project_id)}, [("name", 1)])


class FlatService(BaseService):
    collection_name = "flats"
    project_scoped = True
    BLOCKED_STATUSES = ("Blocked", "Mortgage")

    @classmethod
    def filter(cls, params):
        def parse_number(value, number_type=int):
            try:
                return number_type(value)
            except (TypeError, ValueError):
                return None

        query = {}
        for key in ("project_id", "tower_id", "facing"):
            if params.get(key):
                query[key] = params[key]
        if params.get("status"):
            query["status"] = {"$in": cls.BLOCKED_STATUSES} if params["status"] == "Blocked" else params["status"]
        if params.get("floor"):
            floor = parse_number(params["floor"])
            if floor is not None:
                query["floor"] = floor
        if params.get("flat_no"):
            query["flat_no"] = {"$regex": params["flat_no"].strip(), "$options": "i"}
        if params.get("sft_min") or params.get("sft_max"):
            query["sft"] = {}
            if params.get("sft_min"):
                sft_min = parse_number(params["sft_min"])
                if sft_min is not None:
                    query["sft"]["$gte"] = sft_min
            if params.get("sft_max"):
                sft_max = parse_number(params["sft_max"])
                if sft_max is not None:
                    query["sft"]["$lte"] = sft_max
            if not query["sft"]:
                query.pop("sft")
        if params.get("price_min") or params.get("price_max"):
            price_range = {}
            if params.get("price_min"):
                price_min = parse_number(params["price_min"], float)
                if price_min is not None:
                    price_range["$gte"] = price_min
            if params.get("price_max"):
                price_max = parse_number(params["price_max"], float)
                if price_max is not None:
                    price_range["$lte"] = price_max
            if price_range:
                query["$or"] = [{"price": price_range}, {"base_price": price_range}, {"gross_amount": price_range}]
        return cls.all(query, [("tower", 1), ("floor", 1), ("flat_no", 1)])

    @classmethod
    def status_summary(cls, project_id=None, tower_id=None):
        match = cls.scoped_query({})
        if project_id:
            match["project_id"] = str(project_id)
        if tower_id:
            match["tower_id"] = str(tower_id)
        total = cls.collection().count_documents(match)
        pipeline = [
            {"$match": match},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        counts = {row["_id"] or "Unknown": row["count"] for row in cls.collection().aggregate(pipeline)}
        blocked = sum(counts.get(status, 0) for status in cls.BLOCKED_STATUSES)
        return {
            "total": total,
            "available": counts.get("Available", 0),
            "sold": counts.get("Sold", 0),
            "blocked": blocked,
            "reserved": counts.get("Reserved", 0),
            "cancelled": counts.get("Cancelled", 0),
        }

    @classmethod
    def tower_summaries(cls, project_id):
        towers = TowerService.by_project(project_id)
        summaries = []
        for tower in towers:
            stats = cls.status_summary(project_id=project_id, tower_id=tower["_id"])
            summaries.append({**tower, "stats": stats})
        return summaries

    @classmethod
    def generate_inventory(cls, project_id, tower_id, tower_name, floors, pattern_rows):
        generated = []
        for floor in range(1, int(floors) + 1):
            for row in pattern_rows:
                seed_no = row["flat_no"].strip().upper()
                suffix = "".join(ch for ch in seed_no if ch.isdigit())[-2:]
                prefix = "".join(ch for ch in seed_no if not ch.isdigit())
                flat_no = f"{prefix}{floor}{suffix}"
                data = {
                    "project_id": project_id,
                    "tower_id": tower_id,
                    "project": row.get("project", ""),
                    "tower": tower_name,
                    "flat_no": flat_no,
                    "floor": floor,
                    "sft": int(row["sft"]),
                    "facing": row["facing"],
                    "status": "Available",
                    "availability": "Available",
                    "customer_id": None,
                    "booking_id": None,
                }
                cls.collection().update_one(
                    cls.scoped_query({"project_id": project_id, "tower_id": tower_id, "flat_no": flat_no}),
                    {"$setOnInsert": data},
                    upsert=True,
                )
                generated.append(data)
        return generated

    @classmethod
    def mark_sold(cls, flat_id):
        cls.collection().update_one(cls.scoped_query({"_id": ObjectId(flat_id)}), {"$set": {"status": "Sold", "availability": "Sold"}})

    @classmethod
    def link_booking(cls, flat_id, customer_id, booking_id):
        cls.collection().update_one(
            cls.scoped_query({"_id": ObjectId(flat_id)}),
            {"$set": {
                "status": "Sold",
                "availability": "Sold",
                "customer_id": customer_id,
                "booking_id": booking_id,
            }},
        )
