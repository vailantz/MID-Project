"""Stage observations, reconcile known identities and populate the two local sources."""

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from itertools import groupby, islice
import argparse
import csv
import json
import sqlite3
import regex
import requests
from rules import normalize, resolve
from quotes import (
    documents as quote_documents,
    eligible_properties,
    read_quotes,
    POLICIES,
)
from support import (
    ROOT,
    DATA,
    REPORTS,
    DATABASE,
    INDEX,
    PEOPLE_INDEX,
    CONTRACT,
    COUNTRIES,
    checksum,
    clean_text,
    es,
    mongo,
    read_json,
    report_run,
    require_ready,
    save_json,
    scan,
    text_key,
    writer_lock,
)


def prepare_stage():
    path = ROOT / ".runtime/stage.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript(
        "CREATE TABLE observations(kind TEXT, entity TEXT, payload TEXT);"
        "CREATE TABLE profiles(person_id TEXT PRIMARY KEY, payload TEXT);"
        "CREATE TABLE canonical_reviews(review_id TEXT PRIMARY KEY, person_id TEXT, listing_id TEXT, payload TEXT);"
    )
    batch = []
    stats = Counter()
    rejected = (REPORTS / "quarantined_records.jsonl").open("w", encoding="utf-8")

    def add(kind, raw):
        try:
            values, flags = normalize(raw, kind)
            identity = raw["review_id"] if kind == "review" else raw["listing_id"]
            person = raw["person_id"] if kind == "review" else raw["host_person_id"]
            profile_raw = {
                "person_id": person,
                "name": (
                    raw.get("reviewer_name")
                    if kind == "review"
                    else raw.get("host_name")
                ),
                "phone": (
                    raw.get("reviewer_phone")
                    if kind == "review"
                    else raw.get("host_phone")
                ),
                "country": None if kind == "review" else raw.get("host_phone_country"),
                "observed_at": raw.get("observed_at"),
                "role": "reviewer" if kind == "review" else "host",
            }
            profile, pflags = normalize(profile_raw, "person")
            entry = {
                "record_id": raw["record_id"],
                "raw": raw,
                "values": values,
                "flags": sorted(set(flags + pflags)),
            }
            batch.append((kind, identity, json.dumps(entry, ensure_ascii=False)))
            batch.append(
                (
                    "person",
                    person,
                    json.dumps(
                        {
                            "record_id": raw["record_id"],
                            "raw": profile_raw,
                            "values": profile,
                            "flags": pflags,
                            "role": "reviewer" if kind == "review" else "host",
                        },
                        ensure_ascii=False,
                    ),
                )
            )
            stats[kind + "_observations"] += 1
            if len(batch) >= 2000:
                db.executemany("INSERT INTO observations VALUES(?,?,?)", batch)
                batch.clear()
        except (ValueError, KeyError, TypeError) as error:
            rejected.write(
                json.dumps({"reason": str(error), "raw": raw}, ensure_ascii=False)
                + "\n"
            )
            stats["rejected_records"] += 1

    try:
        with (DATA / "79189_1.csv").open(encoding="utf-8-sig", newline="") as f:
            for i, raw in enumerate(csv.DictReader(f), 1):
                add("review", raw)
                if i % 250000 == 0:
                    db.commit()
                    print(f"Staged {i:,} review observations.", flush=True)
        for raw in read_json(DATA / "79189_2.json"):
            add("property", raw)
        if batch:
            db.executemany("INSERT INTO observations VALUES(?,?,?)", batch)
        db.commit()
        db.execute("CREATE INDEX observation_identity ON observations(kind,entity)")
        db.commit()
    finally:
        rejected.close()
    return db, stats


def families(db, kind):
    rows = db.execute(
        "SELECT entity,payload FROM observations WHERE kind=? ORDER BY entity", (kind,)
    )
    for key, group in groupby(rows, key=lambda row: row[0]):
        yield key, [json.loads(row[1]) for row in group]


def bulk(index, documents):
    lines = []
    for key, doc in documents:
        lines.extend(
            [
                json.dumps({"index": {"_index": index, "_id": key}}),
                json.dumps(doc, ensure_ascii=False),
            ]
        )
        if len(lines) >= 1000:
            es("POST", "_bulk", lines=lines)
            lines = []
    if lines:
        es("POST", "_bulk", lines=lines)


def vector_cache():
    cache = {}
    for index in (INDEX, "dmi-79189-reviews-quality", "dmi-79189-reviews"):
        try:
            mapping = next(iter(es("GET", index + "/_mapping").values()))["mappings"]
        except requests.HTTPError as error:
            if error.response.status_code == 404:
                continue
            raise
        if mapping.get("_meta", {}).get("embedding_contract") != CONTRACT:
            continue
        records = scan(
            index, {"exists": {"field": "embedding"}}, size=256, exclude_vectors=False
        )
        try:
            for hit in islice(records, 10000):
                cache.setdefault(
                    text_key(hit["_source"].get("comments")),
                    hit["_source"]["embedding"],
                )
        finally:
            records.close()
    return cache


def bson_dates(doc):
    def convert(value):
        return (
            datetime.strptime(
                value, "%Y-%m-%dT%H:%M:%SZ" if "T" in value else "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)
            if value
            else None
        )

    doc = deepcopy(doc)
    doc["observed_at"] = convert(doc["observed_at"])
    if "last_scraped" in doc:
        doc["last_scraped"] = convert(doc["last_scraped"])
        for field in ("first_date", "last_date"):
            doc["review_summary"][field] = convert(doc["review_summary"].get(field))
    return doc


def ingest(reset):
    manifest = read_json(REPORTS / "preparation.json")
    if manifest.get("status") != "PASS":
        raise RuntimeError("Run data.py successfully first.")
    for name, digest in manifest["sha256"].items():
        if checksum(DATA / name) != digest:
            raise ValueError("Prepared input changed: " + name)
    from owners import load_prepared

    owner_input = load_prepared()
    with mongo() as client:
        database = client[DATABASE]
        indices = es("GET", "_cat/indices?format=json")
        if (
            database.list_collection_names()
            or any(d["index"] in (INDEX, PEOPLE_INDEX) for d in indices)
        ) and not reset:
            raise RuntimeError(
                "Sources exist. Use --reset to replace only the v2 sources."
            )
        cache = vector_cache()
        db, stats = prepare_stage()
        metadata = {
            "schema_version": 3,
            "embedding_contract": CONTRACT,
            "sha256": manifest["sha256"]["79189_1.csv"],
            "source_sha256": manifest["sha256"],
            "ingestion_complete": False,
        }
        for index, file in [(INDEX, "reviews.json"), (PEOPLE_INDEX, "people.json")]:
            try:
                es("DELETE", index)
            except requests.HTTPError as error:
                if error.response.status_code != 404:
                    raise
            definition = read_json(ROOT / "database" / file)
            definition["mappings"]["_meta"] = metadata
            es("PUT", index, definition)
        database.state.replace_one(
            {"_id": "ingestion"}, {"_id": "ingestion", "ready": False}, upsert=True
        )
        for collection in ("accommodation", "people", "owners", "price_quotes"):
            database.drop_collection(collection)
            database.create_collection(
                collection,
                validator=read_json(
                    ROOT / "database" / (collection + "_validator.json")
                ),
            )
        mongo_people = []

        def profiles():
            for key, observations in families(db, "person"):
                d = resolve(observations, ["name", "phone"])
                d.update(person_id=key, roles=sorted({o["role"] for o in observations}))
                d["quality_flags"] = [
                    f
                    for f in d["quality_flags"]
                    if f not in ("exact_duplicate_observation", "multiple_observations")
                ]
                db.execute(
                    "INSERT INTO profiles VALUES(?,?)",
                    (key, json.dumps(d, ensure_ascii=False)),
                )
                if "host" in d["roles"]:
                    phone = d["phone"]
                    country = next(
                        (
                            c
                            for c in COUNTRIES
                            if phone and phone.startswith("+" + c[3] + " ")
                        ),
                        None,
                    )
                    host = {
                        **d,
                        "_id": key,
                        "phone_number": phone.split(" ")[1] if phone else None,
                        "phone_country": country[1] if country else None,
                    }
                    host.pop("phone")
                    mongo_people.append(bson_dates(host))
                    if len(mongo_people) >= 500:
                        database.people.insert_many(mongo_people)
                        mongo_people.clear()
                stats["people"] += 1
                yield key, d
            if mongo_people:
                database.people.insert_many(mongo_people)

        try:
            bulk(PEOPLE_INDEX, profiles())
            db.commit()
            valid_properties = {
                row[0]
                for row in db.execute(
                    "SELECT DISTINCT entity FROM observations WHERE kind='property'"
                )
            }
            counts = Counter()
            quiet = Counter()
            review_flags = Counter()

            def reviews():
                for key, observations in families(db, "review"):
                    links = {
                        (o["values"]["listing_id"], o["values"]["person_id"])
                        for o in observations
                    }
                    if len(links) != 1:
                        raise ValueError("Conflicting identity for review " + key)
                    listing, person = links.pop()
                    if (
                        listing not in valid_properties
                        or not db.execute(
                            "SELECT 1 FROM profiles WHERE person_id=?", (person,)
                        ).fetchone()
                    ):
                        raise ValueError("Dangling review reference " + key)
                    d = resolve(observations, ["date", "comments", "review_score"])
                    d.update(review_id=key, listing_id=listing, person_id=person)
                    vector = (
                        cache.get(text_key(d["comments"])) if d["comments"] else None
                    )
                    if vector is not None:
                        d["embedding"] = vector
                        stats["reused_vectors"] += 1
                    review_flags.update(d["quality_flags"])
                    counts[listing] += 1
                    if (
                        d["date"]
                        and d["date"] >= "2025-01-01"
                        and regex.search(
                            r"\bquiet\b",
                            clean_text(d["comments"]),
                            regex.I | regex.WORD,
                        )
                    ):
                        quiet[listing] += 1
                    db.execute(
                        "INSERT INTO canonical_reviews VALUES(?,?,?,?)",
                        (
                            key,
                            person,
                            listing,
                            json.dumps(
                                {k: v for k, v in d.items() if k != "embedding"},
                                ensure_ascii=False,
                            ),
                        ),
                    )
                    stats["reviews"] += 1
                    if stats["reviews"] % 250000 == 0:
                        print(
                            f"Loaded {stats['reviews']:,} logical reviews.", flush=True
                        )
                    yield key, d

            bulk(INDEX, reviews())
            db.commit()
            property_flags = Counter()
            documents = []
            quote_batch = []
            for key, observations in families(db, "property"):
                host_ids = {o["values"]["host_person_id"] for o in observations}
                if len(host_ids) != 1:
                    raise ValueError("Conflicting host reference " + key)
                fields = [
                    k
                    for k in observations[0]["values"]
                    if k
                    not in ("record_id", "listing_id", "observed_at", "host_person_id")
                ]
                d = resolve(observations, fields)
                host_person_id = host_ids.pop()
                d.update(
                    _id=key,
                    listing_id=key,
                    host_person_id=host_person_id,
                    owner_id="O" + host_person_id[1:],
                )
                d["ratings"] = d["ratings"] or dict.fromkeys(
                    [
                        "rating",
                        "accuracy",
                        "cleanliness",
                        "checkin",
                        "communication",
                        "location",
                        "value",
                    ]
                )
                d["location"] = d["location"] or {
                    "municipality": None,
                    "neighbourhood": None,
                }
                pair = d.pop("position")
                d["location"].update(
                    latitude=pair[1] if pair else None,
                    longitude=pair[0] if pair else None,
                    point={"type": "Point", "coordinates": pair} if pair else None,
                )
                d["amenities"] = d["amenities"] or []
                d["review_summary"]["indexed_count"] = counts[key]
                if d["review_summary"]["count"] != counts[key]:
                    d["quality_flags"].append("review_count_mismatch")
                quotes = quote_documents(observations, key)
                quote_batch.extend(quotes)
                if len(quote_batch) >= 500:
                    database.price_quotes.insert_many(quote_batch)
                    quote_batch.clear()
                stats["price_quotes"] += len(quotes)
                stats["quote_observations"] += sum(
                    len(q["observations"]) for q in quotes
                )
                property_flags.update(d["quality_flags"])
                documents.append(bson_dates(d))
                stats["properties"] += 1
            if quote_batch:
                database.price_quotes.insert_many(quote_batch)
            for start in range(0, len(documents), 500):
                database.accommodation.insert_many(documents[start : start + 500])
            database.accommodation.create_index("listing_id", unique=True)
            database.accommodation.create_index("location.municipality")
            database.price_quotes.create_index("quote_id", unique=True)
            database.price_quotes.create_index([("listing_id", 1), ("origin", 1)])
            database.accommodation.create_index([("location.point", "2dsphere")])
            database.accommodation.create_index("host_person_id")
            database.people.create_index("person_id", unique=True)
            from align_owners import install

            install(owner_input, database)
            stats["owners"] = len(owner_input)
            for index in (INDEX, PEOPLE_INDEX):
                es("PUT", index + "/_settings", {"index": {"refresh_interval": "1s"}})
                es("POST", index + "/_refresh")
            if (
                es("GET", INDEX + "/_count")["count"] != stats["reviews"]
                or es("GET", PEOPLE_INDEX + "/_count")["count"] != stats["people"]
            ):
                raise AssertionError("Incomplete Elasticsearch population")
            if database.accommodation.count_documents({}) != stats["properties"]:
                raise AssertionError("Incomplete property population")
            if (
                database.price_quotes.count_documents({})
                != manifest["price_quotes"]["logical_quotes"]
            ):
                raise AssertionError("Incomplete price-quote population")
            if stats["quote_observations"] != manifest["price_quotes"]["observations"]:
                raise AssertionError("Incomplete price-quote history")
            save_json(
                REPORTS / "expected_queries.json",
                {"quiet_counts": dict(quiet)},
            )
            database.state.update_one(
                {"_id": "ingestion"},
                {
                    "$set": {
                        "ready": True,
                        "source_sha256": manifest["sha256"],
                        "quote_schema_version": 1,
                    }
                },
            )
            for index in (INDEX, PEOPLE_INDEX):
                es(
                    "PUT",
                    index + "/_mapping",
                    {"_meta": {**metadata, "ingestion_complete": True}},
                )
            return {
                "counts": dict(stats),
                "review_flags": dict(review_flags),
                "property_flags": dict(property_flags),
                "host_people": database.people.count_documents({}),
                "source_sha256": manifest["sha256"],
            }
        finally:
            db.close()


def search(text):
    require_ready()
    result = es(
        "POST",
        INDEX + "/_search",
        {
            "size": 5,
            "_source": {"excludes": ["embedding"]},
            "query": {"match": {"comments": text}},
            "highlight": {"fields": {"comments": {}}},
        },
    )
    ids = list({h["_source"]["person_id"] for h in result["hits"]["hits"]})
    people = (
        {
            d["_id"]: d["_source"]
            for d in es("POST", PEOPLE_INDEX + "/_mget", {"ids": ids})["docs"]
            if d.get("found")
        }
        if ids
        else {}
    )
    return [
        {
            "review": h["_source"],
            "person": people.get(h["_source"]["person_id"]),
            "score": h["_score"],
            "highlights": h.get("highlight", {}),
        }
        for h in result["hits"]["hits"]
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--search")
    parser.add_argument("--properties", action="store_true")
    parser.add_argument("--owners", action="store_true")
    parser.add_argument("--renewals", action="store_true")
    parser.add_argument("--owner-id")
    parser.add_argument("--as-of")
    parser.add_argument("--quotes", metavar="LISTING_ID")
    parser.add_argument("--quote-policy", choices=POLICIES, default="latest-valid")
    parser.add_argument("--checkin")
    parser.add_argument("--checkout")
    args = parser.parse_args()
    if (args.checkin is not None or args.checkout is not None) and args.quotes is None:
        parser.error("Stay-date filters require --quotes")
    if args.owners or args.renewals or args.owner_id:
        from owners import read_owners

        require_ready()
        with mongo() as client:
            try:
                result = read_owners(
                    client[DATABASE], args.as_of, args.renewals, args.owner_id
                )
            except ValueError as error:
                parser.error(str(error))
        print(json.dumps(result, default=str, ensure_ascii=True))
    elif args.as_of:
        parser.error("--as-of requires --owners, --renewals or --owner-id")
    elif args.search is not None:
        if not args.search.strip():
            parser.error("Search text must not be empty")
        print(json.dumps(search(args.search), ensure_ascii=True, default=str))
    elif args.quotes is not None:
        require_ready()
        with mongo() as client:
            try:
                result = read_quotes(
                    client[DATABASE],
                    args.quotes,
                    args.quote_policy,
                    args.checkin,
                    args.checkout,
                )
            except ValueError as error:
                parser.error(str(error))
        print(json.dumps(result, default=str, ensure_ascii=True))
    elif args.properties:
        require_ready()
        with mongo() as client:
            result = eligible_properties(client[DATABASE], args.quote_policy)[:5]
            for row in result:
                row["host"] = client[DATABASE].people.find_one(
                    {"person_id": row["property"]["host_person_id"]}
                )
        print(json.dumps(result, default=str, ensure_ascii=True))
    else:
        with writer_lock(), report_run("ingestion") as report:
            report.update(ingest(args.reset))
