"""Run the numbered read-only queries in docs/anomalies_and_handling.pdf."""

import argparse
import json

from support import DATABASE, es, mongo, require_ready
from owners import document_status
from quotes import select_quote

EXAMPLES = {
    1: {
        "kind": "mongodb",
        "collection": "people",
        "filter": {
            "person_id": "P011f108de937e2339ca251c3"
        },
        "projection": {
            "_id": 0,
            "person_id": 1,
            "phone_country": 1,
            "phone_number": 1
        }
    },
    2: {
        "kind": "elasticsearch",
        "index": "dmi-79189-v2-people",
        "path": "_search",
        "body": {
            "size": 1,
            "_source": [
                "person_id",
                "phone"
            ],
            "query": {
                "term": {
                    "person_id": "P011f108de937e2339ca251c3"
                }
            }
        }
    },
    3: {
        "kind": "elasticsearch",
        "index": "dmi-79189-v2-people",
        "path": "_search",
        "body": {
            "size": 1,
            "_source": [
                "person_id",
                "name"
            ],
            "query": {
                "term": {
                    "person_id": "P0032dbddf24a007688fb3072"
                }
            }
        }
    },
    4: {
        "kind": "mongodb",
        "collection": "people",
        "filter": {
            "person_id": "P005127723dc03aa009c8f74f"
        },
        "projection": {
            "_id": 0,
            "person_id": 1,
            "phone_country": 1,
            "phone_number": 1
        }
    },
    5: {
        "kind": "mongodb",
        "collection": "people",
        "filter": {
            "person_id": "P1d14840a054f2ea969aac1d0"
        },
        "projection": {
            "_id": 0,
            "person_id": 1,
            "observations.raw.phone": 1,
            "observations.occurrences": 1
        }
    },
    6: {
        "kind": "elasticsearch",
        "index": "dmi-79189-v2-people",
        "path": "_count",
        "body": {
            "query": {
                "term": {
                    "phone": "+1 2122049312"
                }
            }
        }
    },
    7: {
        "kind": "owner",
        "owner_id": "O0011d02305bbdf9263e190de",
        "as_of": "2026-10-17"
    },
    8: {
        "kind": "owner",
        "owner_id": "O0011d02305bbdf9263e190de",
        "as_of": "2026-10-18"
    },
    9: {
        "kind": "mongodb",
        "collection": "accommodation",
        "filter": {
            "listing_id": "1126728012230155461"
        },
        "projection": {
            "_id": 0,
            "listing_id": 1,
            "ratings.rating": 1
        }
    },
    10: {
        "kind": "mongodb",
        "collection": "accommodation",
        "filter": {
            "listing_id": "834674"
        },
        "projection": {
            "_id": 0,
            "listing_id": 1,
            "location.latitude": 1,
            "location.longitude": 1,
            "resolution.position": 1
        }
    },
    11: {
        "kind": "mongodb",
        "collection": "accommodation",
        "filter": {
            "listing_id": "1444180500222834990"
        },
        "projection": {
            "_id": 0,
            "listing_id": 1,
            "location.latitude": 1,
            "location.longitude": 1,
            "resolution.position": 1
        }
    },
    12: {
        "kind": "elasticsearch",
        "index": "dmi-79189-v2-reviews",
        "path": "_search",
        "body": {
            "size": 1,
            "_source": [
                "review_id",
                "listing_id",
                "comments",
                "embedding_status"
            ],
            "query": {
                "term": {
                    "review_id": "R1170378700108809611-1424621554075546935"
                }
            }
        }
    },
    13: {
        "kind": "elasticsearch",
        "index": "dmi-79189-v2-reviews",
        "path": "_search",
        "body": {
            "size": 1,
            "_source": [
                "review_id",
                "review_score",
                "resolution.review_score"
            ],
            "query": {
                "term": {
                    "review_id": "R11710930-210435381"
                }
            }
        }
    },
    14: {
        "kind": "elasticsearch",
        "index": "dmi-79189-v2-reviews",
        "path": "_search",
        "body": {
            "size": 1,
            "_source": [
                "review_id",
                "review_score",
                "resolution.review_score"
            ],
            "query": {
                "term": {
                    "review_id": "R89015-196243092"
                }
            }
        }
    },
    15: {
        "kind": "elasticsearch",
        "index": "dmi-79189-v2-reviews",
        "path": "_search",
        "body": {
            "size": 1,
            "_source": [
                "review_id",
                "comments",
                "resolution.comments"
            ],
            "query": {
                "term": {
                    "review_id": "R1196285916567997317-1357200267227288812"
                }
            }
        }
    },
    16: {
        "kind": "elasticsearch",
        "index": "dmi-79189-v2-reviews",
        "path": "_search",
        "body": {
            "size": 1,
            "_source": [
                "review_id",
                "observations.occurrences"
            ],
            "query": {
                "term": {
                    "review_id": "R103252-440885970"
                }
            }
        }
    },
    17: {
        "kind": "quote",
        "quote_id": "Q1021678475590952703-source",
        "policy": "latest-valid"
    },
    18: {
        "kind": "quote",
        "quote_id": "Q1127443-demo",
        "policy": "latest-valid"
    },
    19: {
        "kind": "quote",
        "quote_id": "Q1013904-demo",
        "policy": "latest-valid"
    },
    20: {
        "kind": "quote",
        "quote_id": "Q1013904-demo",
        "policy": "agreement-only"
    },
    21: {
        "kind": "quote",
        "quote_id": "Q3250100-demo",
        "policy": "latest-valid"
    },
}


def run(number):
    query = EXAMPLES[number]
    if query["kind"] == "elasticsearch":
        result = es("POST", query["index"] + "/" + query["path"], query["body"])
        if query["path"] == "_count":
            return {"count": result["count"]}
        return result["hits"]["hits"][0]["_source"]
    with mongo() as client:
        database = client[DATABASE]
        if query["kind"] == "owner":
            owner = database.owners.find_one({"owner_id": query["owner_id"]})
            return {"owner": document_status(owner, query["as_of"])}
        if query["kind"] == "quote":
            quote = database.price_quotes.find_one({"quote_id": query["quote_id"]})
            return select_quote(quote, query["policy"])
        return database[query["collection"]].find_one(query["filter"], query["projection"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", type=int, choices=EXAMPLES, required=True)
    args = parser.parse_args()
    require_ready()
    print(json.dumps(run(args.query), indent=2, default=str))
