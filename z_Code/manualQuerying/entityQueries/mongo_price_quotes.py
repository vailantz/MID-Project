"""Quote-history template: match one observation's monetary context; no policy selection."""

from bson import Decimal128
from bson.json_util import dumps
from pymongo import MongoClient

URI = "mongodb://127.0.0.1:27017"
DATABASE = "dmi_79189_v2"
COLLECTION = "price_quotes"

FILTER = {
    "origin": {"$in": ["prepared_source", "simulated"]},
    "observations": {"$elemMatch": {
        "values.currency": "EUR",
        "values.amount": {"$gte": Decimal128("50.00"), "$lte": Decimal128("150.00")},
        "values.price_basis": {"$in": ["unspecified", "per_night"]},
    }},
}
PROJECTION = {
    "_id": 0,
    "quote_id": 1,
    "listing_id": 1,
    "origin": 1,
    "observations": {"$slice": 5},
}
SORT = [("listing_id", 1), ("quote_id", 1)]
SKIP = 0
LIMIT = 10


def main():
    if LIMIT < 1 or SKIP < 0:
        raise ValueError("Use a positive LIMIT and a non-negative SKIP.")
    with MongoClient(URI, serverSelectionTimeoutMS=5000) as client:
        collection = client[DATABASE][COLLECTION]
        results = list(collection.find(FILTER, PROJECTION).sort(SORT).skip(SKIP).limit(LIMIT))
        print(dumps({"collection": COLLECTION, "selection": "any matching historical observation",
                     "policy_applied": False, "matched": collection.count_documents(FILTER),
                     "returned": len(results), "skip": SKIP, "limit": LIMIT,
                     "results": results}, indent=2))


if __name__ == "__main__":
    main()
