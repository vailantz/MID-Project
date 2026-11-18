"""Accommodation template: edit FILTER, PROJECTION, SORT, SKIP and LIMIT."""

from bson.json_util import dumps
from pymongo import MongoClient

URI = "mongodb://127.0.0.1:27017"
DATABASE = "dmi_79189_v2"
COLLECTION = "accommodation"

FILTER = {
    "location.municipality": "Lisboa",
    "capacity": {"$gte": 2, "$lte": 8},
    "amenities": {"$all": ["Wifi", "Kitchen"]},
    "ratings.rating": {"$gte": 4.8},
    "room_type": {"$in": ["Entire home/apt", "Private room"]},
}
PROJECTION = {
    "_id": 0,
    "listing_id": 1,
    "name": 1,
    "property_type": 1,
    "room_type": 1,
    "capacity": 1,
    "location": 1,
    "amenities": 1,
    "ratings": 1,
    "review_summary": 1,
    "last_scraped": 1,
    "observed_at": 1,
    "host_person_id": 1,
    "owner_id": 1,
    "quality_flags": 1,
    "resolution": 1,
    "observations": {"$slice": 3},
}
SORT = [("ratings.rating", -1), ("capacity", 1), ("listing_id", 1)]
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
