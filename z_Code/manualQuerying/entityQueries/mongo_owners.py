"""Owner template: native aggregation recalculates expiry for AS_OF; no writes."""

from datetime import datetime, timezone

from bson.json_util import dumps
from pymongo import MongoClient

URI = "mongodb://127.0.0.1:27017"
DATABASE = "dmi_79189_v2"
COLLECTION = "owners"
AS_OF = datetime(2026, 11, 13, tzinfo=timezone.utc)

# active belongs to the stored activity snapshot, not the document check date.
FILTER = {
    "active": True,
    "needs_renewal": True,
    "identity_document.type": {"$in": ["CC", "PASSPORT"]},
    "activity.recent_review_count": {"$gte": 1},
}
PROJECTION = {
    "_id": 0,
    "owner_id": 1,
    "person_id": 1,
    "document_key": 1,
    "identity_document": 1,
    "activity": 1,
    "active": 1,
    "documentation_up_to_date": 1,
    "needs_renewal": 1,
    "reference_dates": 1,
}
SORT = {"identity_document.expires_on": 1, "owner_id": 1}
SKIP = 0
LIMIT = 10


def main():
    if LIMIT < 1 or SKIP < 0:
        raise ValueError("Use a positive LIMIT and a non-negative SKIP.")
    pipeline = [
        {"$set": {
            "documentation_up_to_date": {"$gte": ["$identity_document.expires_on", AS_OF]},
            "needs_renewal": {"$lt": ["$identity_document.expires_on", AS_OF]},
            "reference_dates.status_as_of": AS_OF,
        }},
        {"$match": FILTER},
        {"$facet": {
            "summary": [{"$count": "matched"}],
            "results": [{"$sort": SORT}, {"$skip": SKIP}, {"$limit": LIMIT},
                        {"$project": PROJECTION}],
        }},
    ]
    with MongoClient(URI, serverSelectionTimeoutMS=5000) as client:
        output = next(client[DATABASE][COLLECTION].aggregate(pipeline))
        matched = output["summary"][0]["matched"] if output["summary"] else 0
        results = output["results"]
        print(dumps({"collection": COLLECTION, "as_of": AS_OF, "matched": matched,
                     "returned": len(results), "skip": SKIP, "limit": LIMIT,
                     "results": results}, indent=2))


if __name__ == "__main__":
    main()
