"""Host-profile template: edit FILTER, PROJECTION, SORT, SKIP and LIMIT."""

from bson.json_util import dumps
from pymongo import MongoClient

URI = "mongodb://127.0.0.1:27017"
DATABASE = "dmi_79189_v2"
COLLECTION = "people"

FILTER = {
    "roles": "host",
    "phone_country": {"$in": ["Portugal", "United Kingdom"]},
    "phone_number": {"$ne": None},
}
PROJECTION = {
    "_id": 0,
    "person_id": 1,
    "name": 1,
    "phone_country": 1,
    "phone_number": 1,
    "roles": 1,
    "observed_at": 1,
    "quality_flags": 1,
    "resolution": 1,
    "observations": {"$slice": 3},
}
SORT = [("phone_country", 1), ("name", 1), ("person_id", 1)]
SKIP = 0
LIMIT = 10


def main():
    if LIMIT < 1 or SKIP < 0:
        raise ValueError("Use a positive LIMIT and a non-negative SKIP.")
    with MongoClient(URI, serverSelectionTimeoutMS=5000) as client:
        collection = client[DATABASE][COLLECTION]
        results = list(collection.find(FILTER, PROJECTION).sort(SORT).skip(SKIP).limit(LIMIT))
        print(dumps({"collection": COLLECTION, "matched": collection.count_documents(FILTER),
                     "returned": len(results), "skip": SKIP, "limit": LIMIT,
                     "results": results}, indent=2))


if __name__ == "__main__":
    main()
