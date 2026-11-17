"""Verify live sources against fixed cases, input totals and complete query answers."""

from copy import deepcopy
from collections import Counter
import json
import math
from bson import Decimal128
from pymongo.errors import WriteError
from quotes import eligible_properties, select_quote, read_quotes
from support import (
    ROOT,
    DATA,
    REPORTS,
    DATABASE,
    INDEX,
    PEOPLE_INDEX,
    es,
    mongo,
    read_json,
    report_run,
    require_ready,
)


def run():
    metadata = require_ready()
    expected = read_json(REPORTS / "expected_queries.json")
    prepared = read_json(REPORTS / "preparation.json")
    loaded = read_json(REPORTS / "ingestion.json")
    assert (
        loaded["status"] == "PASS" and metadata["source_sha256"] == prepared["sha256"]
    )
    assert loaded["counts"]["reviews"] == prepared["logical_reviews"]
    assert loaded["counts"]["properties"] == prepared["logical_properties"]
    assert loaded["counts"]["people"] == prepared["person_accounts"]
    for kind in ("review", "property"):
        assert 0.04 < prepared[kind + "_rate"] < 0.06
        n = prepared["issue_multiplicity"][kind]
        assert n["1"] > n["2"] > n["3"]
    with mongo() as client:
        db = client[DATABASE]
        properties = db.accommodation
        ids = sorted(row["property"]["listing_id"] for row in eligible_properties(db))
        expected_ids = []
        prices = {}
        for q in db.price_quotes.find({"origin": "prepared_source"}):
            price = select_quote(q)["price"]
            if (
                price
                and price["currency"] == "EUR"
                and price["price_basis"] == "unspecified"
                and price["amount"].to_decimal() <= 150
            ):
                prices[q["listing_id"]] = price
        for p in properties.find():
            if (
                p["listing_id"] in prices
                and p["location"]["municipality"] == "Lisboa"
                and p["capacity"] >= 2
                and "Wifi" in p["amenities"]
                and p["ratings"]["rating"] is not None
                and p["ratings"]["rating"] >= 4.8
            ):
                expected_ids.append(p["listing_id"])
        assert ids == sorted(expected_ids)
        if prepared["logical_reviews"] == 1950076:
            assert len(ids) == 1930
        assert properties.count_documents({}) == prepared["logical_properties"]
        for field in [
            "ratings.rating",
            "location.latitude",
            "observed_at",
        ]:
            assert properties.count_documents({field: None}) > 0
        assert properties.count_documents({"reference_price": {"$exists": True}}) == 0
        assert properties.count_documents({"ratings.rating": {"$gt": 5}}) == 0
        base = properties.find_one({"location.point": {"$ne": None}})
        nearby = list(
            properties.aggregate(
                [
                    {
                        "$geoNear": {
                            "near": base["location"]["point"],
                            "distanceField": "distance",
                            "maxDistance": 1,
                            "spherical": True,
                            "query": {"listing_id": base["listing_id"]},
                        }
                    }
                ]
            )
        )
        assert len(nearby) == 1 and nearby[0]["distance"] < 0.001
        assert db.people.find_one({"person_id": base["host_person_id"]})
        dangling = list(
            properties.aggregate(
                [
                    {
                        "$lookup": {
                            "from": "people",
                            "localField": "host_person_id",
                            "foreignField": "person_id",
                            "as": "host",
                        }
                    },
                    {"$match": {"host": {"$size": 0}}},
                    {"$limit": 1},
                ]
            )
        )
        assert not dangling
        assert (
            properties.count_documents({"quality_flags": "exact_duplicate_observation"})
            > 0
        )
        assert properties.count_documents({"quality_flags": "changed_position"}) > 0
        quotes = db.price_quotes
        assert quotes.count_documents({}) == prepared["price_quotes"]["logical_quotes"]
        raw_expected = Counter(
            json.dumps(q, sort_keys=True, ensure_ascii=False)
            for p in read_json(DATA / "79189_2.json")
            for q in p["price_quotes"]
        )
        raw_stored = Counter(
            json.dumps(o["raw"], sort_keys=True, ensure_ascii=False)
            for q in quotes.find()
            for o in q["observations"]
        )
        assert raw_stored == raw_expected
        assert sum(raw_stored.values()) == prepared["price_quotes"]["observations"]
        assert not list(
            quotes.aggregate(
                [
                    {
                        "$lookup": {
                            "from": "accommodation",
                            "localField": "listing_id",
                            "foreignField": "listing_id",
                            "as": "property",
                        }
                    },
                    {"$match": {"property": {"$size": 0}}},
                    {"$limit": 1},
                ]
            )
        )
        changed_policy = False
        for q in quotes.find({"origin": "simulated"}):
            before = deepcopy(q)
            latest = select_quote(q)
            agreement = select_quote(q, "agreement-only")
            assert q == before and "price" not in q and "resolution" not in q
            if latest["status"] == "resolved" and agreement["status"] == "unresolved":
                changed_policy = True
                price = latest["price"]
                if price["checkin"] and price["checkout"]:
                    matches = read_quotes(
                        db,
                        q["listing_id"],
                        checkin=price["checkin"].strftime("%Y-%m-%d"),
                        checkout=price["checkout"].strftime("%Y-%m-%d"),
                    )
                    assert q["quote_id"] in {m["quote_id"] for m in matches}
        assert changed_policy
        quote = quotes.find_one()
        validation = db["quote_validation_checks"]
        db.drop_collection(validation.name)
        db.create_collection(
            validation.name,
            validator=read_json(ROOT / "database/price_quotes_validator.json"),
        )
        try:
            for field, value in (
                ("amount", Decimal128("-1")),
                ("observed_at", "not-a-date"),
            ):
                invalid = deepcopy(quote)
                invalid["observations"][0]["values"][field] = value
                try:
                    validation.insert_one(invalid)
                    raise AssertionError("Invalid normalized quote accepted")
                except WriteError as error:
                    assert error.code == 121
        finally:
            db.drop_collection(validation.name)
        test = db["validation_checks"]
        db.drop_collection(test.name)
        db.create_collection(
            test.name,
            validator=read_json(ROOT / "database/accommodation_validator.json"),
        )
        try:
            for update in [
                {"capacity": -1},
                {"ratings": {**base["ratings"], "rating": 8}},
                {"location": {**base["location"], "latitude": None}},
                {"unexpected": True},
            ]:
                try:
                    test.insert_one({**deepcopy(base), **update})
                    raise AssertionError("Invalid canonical property accepted")
                except WriteError as error:
                    assert error.code == 121
        finally:
            db.drop_collection(test.name)
    assert es("GET", INDEX + "/_count")["count"] == prepared["logical_reviews"]
    assert es("GET", PEOPLE_INDEX + "/_count")["count"] == loaded["counts"]["people"]
    for flag in [
        "exact_duplicate_observation",
        "truncated_text_candidate",
        "changed_review_score",
        "unresolved_review_score",
        "invalid_phone",
        "invalid_date",
    ]:
        assert (
            es("POST", INDEX + "/_count", {"query": {"term": {"quality_flags": flag}}})[
                "count"
            ]
            > 0
        ), flag
    # Contacts are not keys: two different profile documents may share one phone.
    shared = es(
        "POST",
        PEOPLE_INDEX + "/_search",
        {
            "size": 0,
            "aggs": {
                "phones": {"terms": {"field": "phone", "min_doc_count": 2, "size": 1}}
            },
        },
    )["aggregations"]["phones"]["buckets"]
    assert shared
    people = es(
        "POST",
        PEOPLE_INDEX + "/_search",
        {"size": 10, "query": {"term": {"phone": shared[0]["key"]}}},
    )["hits"]["hits"]
    assert len({d["_source"]["person_id"] for d in people}) >= 2
    for kind, case in prepared["examples"].items():
        key = case["entity_id"]
        if kind.startswith("review:"):
            document = es("GET", INDEX + "/_doc/" + key)["_source"]
            assert es("GET", PEOPLE_INDEX + "/_doc/" + document["person_id"])["found"]
        else:
            with mongo() as client:
                document = client[DATABASE].accommodation.find_one({"listing_id": key})
        assert document and document["observations"]
    # Independently enumerate complete native aggregation output, including all buckets.
    body = {
        "size": 0,
        "query": {
            "bool": {
                "must": [{"match": {"comments": "quiet"}}],
                "filter": [{"range": {"date": {"gte": "2025-01-01"}}}],
            }
        },
        "aggs": {
            "properties": {
                "composite": {
                    "size": 1000,
                    "sources": [{"listing_id": {"terms": {"field": "listing_id"}}}],
                }
            }
        },
    }
    actual = {}
    while True:
        page = es("POST", INDEX + "/_search", body)["aggregations"]["properties"]
        actual.update({b["key"]["listing_id"]: b["doc_count"] for b in page["buckets"]})
        if not page["buckets"] or "after_key" not in page:
            break
        body["aggs"]["properties"]["composite"]["after"] = page["after_key"]
    assert actual == expected["quiet_counts"]
    vectors = es(
        "POST",
        INDEX + "/_search",
        {"size": 1, "query": {"exists": {"field": "embedding"}}},
    )["hits"]["hits"]
    vector_result = "not generated; BM25 and person queries available"
    if vectors:
        v = vectors[0]["_source"]["embedding"]
        assert (
            len(v) == 1024
            and all(math.isfinite(x) for x in v)
            and abs(sum(x * x for x in v) - 1) < 0.001
        )
        hits = es(
            "POST",
            INDEX + "/_search",
            {
                "size": 1,
                "knn": {
                    "field": "embedding",
                    "query_vector": v,
                    "k": 1,
                    "num_candidates": 100,
                },
            },
        )["hits"]["hits"]
        assert hits and hits[0]["_score"] > 0.99
        vector_result = "dimensions, norm and native kNN verified"
    from test_owners import run as check_owners

    owner_results = check_owners()
    return {
        **owner_results,
        "properties": prepared["logical_properties"],
        "reviews": prepared["logical_reviews"],
        "people": loaded["counts"]["people"],
        "property_filter_count": len(expected_ids),
        "recent_quiet_reviews": sum(actual.values()),
        "quiet_listing_groups": sum(n >= 3 for n in actual.values()),
        "person_references": True,
        "shared_phone_not_identity": True,
        "nullable_fields": True,
        "version_conflicts": True,
        "native_constraints": True,
        "geospatial_query": True,
        "complete_query_answers": True,
        "price_quotes": prepared["price_quotes"]["logical_quotes"],
        "quote_observations": prepared["price_quotes"]["observations"],
        "quote_history_preserved": True,
        "quote_policy_at_retrieval": True,
        "vectors": vector_result,
    }


if __name__ == "__main__":
    with report_run("tests") as report:
        report.update(run())
    print("PASS: live database checks completed.", flush=True)
