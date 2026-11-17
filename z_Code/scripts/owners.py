"""Prepare owner identities and dated activity/document assessments."""

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from itertools import groupby
from pathlib import Path
import csv
import re
import sqlite3
import tempfile

from rules import date_value, resolve
from support import DATA, ROOT, REPORTS, checksum, read_json, save_json

SINCE = "2025-01-01"
AS_OF = "2026-11-13"
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def calendar(value):
    """Document dates have a separate 1900–2199 domain."""
    if isinstance(value, datetime):
        value = value.date().isoformat()
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value
    ):
        raise ValueError("Use a calendar date in YYYY-MM-DD format")
    result = date.fromisoformat(value)
    if not 1900 <= result.year <= 2199:
        raise ValueError("Document date outside 1900–2199")
    return result


def cc_valid(number):
    if not isinstance(number, str) or not re.fullmatch(
        r"[0-9]{9}[A-Z0-9]{2}[0-9]", number
    ):
        return False
    total = 0
    for i, char in enumerate(reversed(number)):
        value = ALPHABET.index(char) * (2 if i % 2 else 1)
        total += value - 9 if i % 2 and value >= 10 else value
    return total % 10 == 0


def identity_document(index, portuguese, expires):
    if portuguese:
        digits = f"{10000000 + index:08}"
        civil_check = (
            11 - sum(int(c) * (9 - i) for i, c in enumerate(digits)) % 11
        ) % 10
        prefix = digits + str(civil_check) + "ZZ"
        number = next(prefix + str(i) for i in range(10) if cc_valid(prefix + str(i)))
    else:
        number = f"{900000000 + index:09}"
    return {
        "issuing_country": "PT" if portuguese else "GB",
        "type": "CC" if portuguese else "PASSPORT",
        "number": number,
        "nationality": "Portuguese" if portuguese else "British",
        "expires_on": expires,
        "is_synthetic": True,
    }


def validate_document(document):
    if not isinstance(document, dict):
        raise ValueError("Missing owner identification document")
    country, kind, number = (
        document.get(k) for k in ("issuing_country", "type", "number")
    )
    valid = (
        country == "PT"
        and kind == "CC"
        and document.get("nationality") == "Portuguese"
        and cc_valid(number)
    ) or (
        country == "GB"
        and kind == "PASSPORT"
        and document.get("nationality") == "British"
        and isinstance(number, str)
        and re.fullmatch(r"[0-9]{9}", number)
    )
    if not valid or document.get("is_synthetic") is not True:
        raise ValueError("Invalid or unlabelled synthetic owner document")
    calendar(document.get("expires_on"))
    return f"{country}:{kind}:{number}"


def property_hosts(properties):
    hosts = {}
    for p in properties:
        listing, person = p["listing_id"], p["host_person_id"]
        if listing in hosts and hosts[listing] != person:
            raise ValueError("Conflicting owner for accommodation " + listing)
        hosts[listing] = person
    return hosts


def activity_from_files():
    """Reconcile publication dates once per logical review without loading the corpus."""
    hosts = property_hosts(read_json(DATA / "79189_2.json"))
    result = defaultdict(
        lambda: {"recent_review_count": 0, "latest_publication_date": None}
    )
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temp:
        db = sqlite3.connect(str(Path(temp) / "dates.sqlite"))
        try:
            db.execute(
                "CREATE TABLE dates(review TEXT, listing TEXT, publication TEXT, observed TEXT)"
            )
            with (DATA / "79189_1.csv").open(encoding="utf-8-sig", newline="") as f:
                batch = []
                for raw in csv.DictReader(f):
                    batch.append(
                        (
                            raw["review_id"],
                            raw["listing_id"].removeprefix("LIS-"),
                            date_value(raw["date"]),
                            date_value(raw["observed_at"], True),
                        )
                    )
                    if len(batch) == 5000:
                        db.executemany("INSERT INTO dates VALUES(?,?,?,?)", batch)
                        batch.clear()
                db.executemany("INSERT INTO dates VALUES(?,?,?,?)", batch)
            db.execute("CREATE INDEX review_key ON dates(review)")
            for key, records in groupby(
                db.execute(
                    "SELECT review,listing,publication,observed FROM dates ORDER BY review"
                ),
                lambda x: x[0],
            ):
                rows = list(records)
                if len({row[1] for row in rows}) != 1 or rows[0][1] not in hosts:
                    raise ValueError("Invalid owner activity reference " + key)
                observations = [
                    {
                        "record_id": key,
                        "raw": {"date": row[2], "observed_at": row[3]},
                        "values": {"date": row[2], "observed_at": row[3]},
                        "flags": [],
                    }
                    for row in rows
                ]
                published = resolve(observations, ["date"])["date"]
                if published and published <= AS_OF:
                    d = result[rows[0][1]]
                    d["recent_review_count"] += published >= SINCE
                    d["latest_publication_date"] = max(
                        d["latest_publication_date"] or published, published
                    )
        finally:
            db.close()
    return hosts, dict(result)


def generate(hosts, listing_activity):
    by_person = defaultdict(list)
    for listing, person in hosts.items():
        by_person[person].append(listing)
    ranked = sorted(
        by_person, key=lambda p: sha256(("owner:" + p).encode()).hexdigest()
    )
    pt = set(ranked[: round(len(ranked) * 6693 / 9484)])
    facts = {}
    for person, listings in by_person.items():
        dates = [
            listing_activity.get(k, {}).get("latest_publication_date") for k in listings
        ]
        dates = [d[:10] for d in dates if d]
        facts[person] = {
            "accommodation_count": len(listings),
            "recent_review_count": sum(
                listing_activity.get(k, {}).get("recent_review_count", 0)
                for k in listings
            ),
            "latest_publication_date": max(dates, default=None),
            "period_start": SINCE,
            "assessment_date": AS_OF,
        }
    active = [p for p in ranked if facts[p]["recent_review_count"] > 0]
    inactive = [p for p in ranked if facts[p]["recent_review_count"] == 0]
    expired = set(
        active[: min(30, len(active))] + inactive[: round(len(inactive) * 357 / 1664)]
    )
    records = []
    for i, person in enumerate(ranked):
        expiry = calendar(AS_OF) + timedelta(
            days=-(i % 365 + 1) if person in expired else 365 + i % 1825
        )
        document = identity_document(i, person in pt, expiry.isoformat())
        owner = {
            "_id": "O" + person[1:],
            "owner_id": "O" + person[1:],
            "person_id": person,
            "document_key": validate_document(document),
            "identity_document": document,
            "activity": facts[person],
            "active": facts[person]["recent_review_count"] > 0,
            "documentation_up_to_date": person not in expired,
            "needs_renewal": person in expired,
            "reference_dates": {"activity_as_of": AS_OF, "status_as_of": AS_OF},
        }
        records.append(owner)
    validate_owners(records, hosts)
    return records


def validate_owners(records, hosts):
    seen_person, seen_owner, seen_document = set(), set(), set()
    property_counts = Counter(hosts.values())
    for owner in records:
        key = validate_document(owner.get("identity_document"))
        person = owner["person_id"]
        if not isinstance(person, str) or not re.fullmatch(r"P[0-9a-f]{24}", person):
            raise ValueError("Invalid owner person reference")
        if owner["owner_id"] != "O" + person[1:] or owner["_id"] != owner["owner_id"]:
            raise ValueError("Owner identity disagrees with person")
        if (
            person in seen_person
            or key in seen_document
            or owner["owner_id"] in seen_owner
        ):
            raise ValueError("Repeated or inconsistent owner/document identity")
        seen_person.add(person)
        seen_owner.add(owner["owner_id"])
        seen_document.add(key)
        a = owner["activity"]
        start, end = calendar(a["period_start"]), calendar(a["assessment_date"])
        latest = (
            calendar(a["latest_publication_date"])
            if a["latest_publication_date"]
            else None
        )
        count = a["recent_review_count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("Invalid owner activity count")
        if (
            start > end
            or (latest and latest > end)
            or ((count > 0) != (latest is not None and start <= latest <= end))
        ):
            raise ValueError("Contradictory owner activity dates")
        if calendar(owner["reference_dates"]["activity_as_of"]) != end:
            raise ValueError("Owner assessment dates differ")
        if a["accommodation_count"] != property_counts[person]:
            raise ValueError("Owner property count disagrees")
        if key != owner["document_key"] or owner["active"] != (
            a["recent_review_count"] > 0
        ):
            raise ValueError("Contradictory owner state")
        current = calendar(owner["identity_document"]["expires_on"]) >= calendar(
            owner["reference_dates"]["status_as_of"]
        )
        if owner["documentation_up_to_date"] != current or owner["needs_renewal"] != (
            not current
        ):
            raise ValueError("Contradictory document state")
    if seen_person != set(hosts.values()):
        raise ValueError("Missing or unexpected owner")


def prepare(listing_activity=None):
    if listing_activity is None:
        hosts, listing_activity = activity_from_files()
    else:
        hosts = property_hosts(read_json(DATA / "79189_2.json"))
    records = generate(hosts, listing_activity)
    save_json(DATA / "owners.json", records)
    report = {
        "status": "PASS",
        "owners": len(records),
        "activity_since": SINCE,
        "assessed_on": AS_OF,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "nationalities": dict(
            Counter(o["identity_document"]["nationality"] for o in records)
        ),
        "states": dict(
            Counter(
                ("active" if o["active"] else "inactive")
                + ("_expired" if o["needs_renewal"] else "_current")
                for o in records
            )
        ),
        "source_sha256": {
            name: checksum(DATA / name) for name in ("79189_1.csv", "79189_2.json")
        },
        "owners_sha256": checksum(DATA / "owners.json"),
        "generated_fields": [
            "synthetic owner identification",
            "expiry lifecycle",
            "dated owner activity",
        ],
    }
    save_json(REPORTS / "owners_preparation.json", report)
    return records


def load_prepared():
    records = read_json(DATA / "owners.json")
    hosts = property_hosts(read_json(DATA / "79189_2.json"))
    validate_owners(records, hosts)
    report = read_json(REPORTS / "owners_preparation.json")
    if report.get("status") != "PASS" or report["owners_sha256"] != checksum(
        DATA / "owners.json"
    ):
        raise ValueError("Owner preparation is incomplete or its input changed")
    if report["source_sha256"] != {
        name: checksum(DATA / name) for name in ("79189_1.csv", "79189_2.json")
    }:
        raise ValueError("Owners were prepared from another input generation")
    return records


def bson_owner(owner):
    d = deepcopy(owner)
    for block, fields in [
        ("identity_document", ["expires_on"]),
        ("activity", ["latest_publication_date", "period_start", "assessment_date"]),
        ("reference_dates", ["activity_as_of", "status_as_of"]),
    ]:
        for field in fields:
            value = d[block][field]
            d[block][field] = (
                datetime.combine(calendar(value), datetime.min.time(), timezone.utc)
                if value
                else None
            )
    return d


def document_status(owner, as_of=None):
    result = deepcopy(owner)
    at = calendar(as_of or date.today().isoformat())
    current = calendar(result["identity_document"]["expires_on"]) >= at
    result.update(documentation_up_to_date=current, needs_renewal=not current)
    result["reference_dates"]["status_as_of"] = at.isoformat()
    return result


def read_owners(database, as_of=None, renewal_only=False, owner_id=None):
    state = database.state.find_one({"_id": "ingestion"}) or {}
    if state.get("owner_schema_version") != 1:
        raise RuntimeError("Load the Owner model with align_owners.py first")
    at = calendar(as_of or date.today().isoformat()).isoformat()
    query = {"owner_id": owner_id} if owner_id else {}
    result = []
    for owner in database.owners.find(query).sort("owner_id", 1):
        owner = document_status(owner, at)
        if renewal_only and not (owner["active"] and owner["needs_renewal"]):
            continue
        result.append(
            {
                "owner": owner,
                "person": database.people.find_one({"person_id": owner["person_id"]}),
                "accommodations": list(
                    database.accommodation.find(
                        {"owner_id": owner["owner_id"]},
                        {
                            "listing_id": 1,
                            "name": 1,
                            "host_person_id": 1,
                            "owner_id": 1,
                        },
                    )
                ),
            }
        )
    return result
