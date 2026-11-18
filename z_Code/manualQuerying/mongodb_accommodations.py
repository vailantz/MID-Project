"""Find five highly rated Lisboa listings with Wifi and capacity for two or more."""

from pymongo import MongoClient
from bson.json_util import dumps


def main():
    with MongoClient("mongodb://127.0.0.1:27017") as client:
        db = client["dmi_79189_v2"]
        results = list(
            db.accommodation.find(
                {
                    "location.municipality": "Lisboa",
                    "capacity": {"$gte": 2},
                    "amenities": "Wifi",
                    "ratings.rating": {"$gte": 4.8},
                },
                {
                    "_id": 0,
                    "listing_id": 1,
                    "name": 1,
                    "capacity": 1,
                    "ratings.rating": 1,
                    "location.municipality": 1,
                    "location.neighbourhood": 1,
                },
            )
            .sort("ratings.rating", -1)
            .limit(5)
        )
        print(dumps(results, indent=2))


if __name__ == "__main__":
    main()
