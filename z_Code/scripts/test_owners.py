"""Check owner identities, source agreement and native document/state constraints."""

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import timedelta
from pymongo.errors import WriteError
from owners import (
    AS_OF,
    SINCE,
    calendar,
    document_status,
    read_owners,
    validate_document,
)
from support import (
    DATABASE,
    INDEX,
    PEOPLE_INDEX,
    ROOT,
    es,
    mongo,
    read_json,
    report_run,
)


def listing_activity():
    result = {}
    after = None
    while True:
        composite = {
            "size": 1000,
            "sources": [{"listing": {"terms": {"field": "listing_id"}}}],
        }
        if after:
            composite["after"] = after
        query = {
            "size": 0,
            "aggs": {
                "listings": {
                    "composite": composite,
                    "aggs": {
                        "recent": {
                            "filter": {"range": {"date": {"gte": SINCE, "lte": AS_OF}}}
                        },
                        "latest": {"max": {"field": "date"}},
                    },
                }
            },
        }
        page = es("POST", INDEX + "/_search", query)["aggregations"]["listings"]
        for row in page["buckets"]:
            result[row["key"]["listing"]] = (
                row["recent"]["doc_count"],
                row["latest"].get("value_as_string"),
            )
        if not page["buckets"] or not page.get("after_key"):
            return result
        after = page["after_key"]


def run():
    per_listing = listing_activity()
    with mongo() as client:
        db = client[DATABASE]
        owners = list(db.owners.find().sort("owner_id", 1))
        people = {p["person_id"]: p for p in db.people.find()}
        properties = list(
            db.accommodation.find(
                {}, {"listing_id": 1, "host_person_id": 1, "owner_id": 1}
            )
        )
        by_owner = defaultdict(list)
        for prop in properties:
            by_owner[prop["owner_id"]].append(prop)
        assert len(owners) == len(people) == len(by_owner)
        keys = set()
        persons = set()
        for owner in owners:
            person = owner["person_id"]
            assert person in people and person not in persons
            persons.add(person)
            key = validate_document(owner["identity_document"])
            assert key == owner["document_key"] and key not in keys
            keys.add(key)
            props = by_owner[owner["owner_id"]]
            assert all(p["host_person_id"] == person for p in props)
            assert len(props) == owner["activity"]["accommodation_count"]
            count = sum(per_listing.get(p["listing_id"], (0, None))[0] for p in props)
            dates = [per_listing.get(p["listing_id"], (0, None))[1] for p in props]
            dates = [d[:10] for d in dates if d]
            latest = owner["activity"]["latest_publication_date"]
            assert (latest.date().isoformat() if latest else None) == max(
                dates, default=None
            )
            assert owner["activity"]["recent_review_count"] == count
            assert owner["active"] == (count > 0)
            assert (
                document_status(owner, AS_OF)["needs_renewal"] == owner["needs_renewal"]
            )
        for start in range(0, len(owners), 500):
            batch = owners[start : start + 500]
            docs = es(
                "POST",
                PEOPLE_INDEX + "/_mget",
                {"ids": [o["person_id"] for o in batch]},
            )["docs"]
            for owner, person in zip(batch, docs):
                assert (
                    person.get("found")
                    and person["_source"]["owner_id"] == owner["owner_id"]
                )
                expected = deepcopy(owner["identity_document"])
                expected["expires_on"] = expected["expires_on"].date().isoformat()
                assert person["_source"]["identity_document"] == expected
        states = Counter(
            ("active" if o["active"] else "inactive")
            + ("_expired" if o["needs_renewal"] else "_current")
            for o in owners
        )
        nations = Counter(o["identity_document"]["nationality"] for o in owners)
        full = (
            read_json(ROOT / "reports/preparation.json")["logical_reviews"] == 1950076
        )
        if full:
            assert len(owners) == 9484 and nations == {
                "Portuguese": 6693,
                "British": 2791,
            }
            assert states == {
                "active_expired": 30,
                "active_current": 7790,
                "inactive_expired": 357,
                "inactive_current": 1307,
            }
        renewal = read_owners(db, AS_OF, True)
        assert len(renewal) == states["active_expired"]
        assert all(r["accommodations"] and r["person"] for r in renewal)
        base = next(o for o in owners if o["identity_document"]["type"] == "CC")
        expiry = calendar(base["identity_document"]["expires_on"])
        before = deepcopy(base)
        assert document_status(base, expiry.isoformat())["documentation_up_to_date"]
        assert document_status(base, (expiry + timedelta(days=1)).isoformat())[
            "needs_renewal"
        ]
        assert base == before
        # Temporary validation collections leave the operational sources untouched.
        name = "owner_validation_checks"
        db.drop_collection(name)
        db.create_collection(
            name, validator=read_json(ROOT / "database/owners_validator.json")
        )
        try:
            db[name].insert_one(base)
            for field in ("owner_id", "person_id", "document_key"):
                db[name].create_index(field, unique=True)
            for change in [
                lambda d: d.update(active=not d["active"]),
                lambda d: d.update(needs_renewal=not d["needs_renewal"]),
                lambda d: d.update(
                    documentation_up_to_date=not d["documentation_up_to_date"]
                ),
                lambda d: d["identity_document"].update(number="000000000ZZ5"),
                lambda d: d["identity_document"].update(issuing_country="GB"),
                lambda d: d["activity"].update(recent_review_count=-1),
                lambda d: (
                    d.update(active=False),
                    d["activity"].update(
                        recent_review_count=0,
                        latest_publication_date=d["activity"]["assessment_date"],
                    ),
                ),
                lambda d: d.pop("identity_document"),
            ]:
                bad = deepcopy(base)
                change(bad)
                try:
                    db[name].replace_one({"_id": base["_id"]}, bad)
                    raise AssertionError("Invalid owner accepted")
                except WriteError as e:
                    assert e.code == 121
            known = deepcopy(base)
            known["identity_document"]["number"] = "000000000ZZ4"
            known["document_key"] = "PT:CC:000000000ZZ4"
            db[name].replace_one({"_id": base["_id"]}, known)
        finally:
            db.drop_collection(name)
    return {
        "owners": len(owners),
        "nationalities": dict(nations),
        "states": dict(states),
        "owner_person_references": True,
        "owner_activity_from_A1": True,
        "document_projection_agreement": True,
        "native_owner_constraints": True,
        "expiry_boundary": True,
        "renewal_query_count": len(renewal),
    }


if __name__ == "__main__":
    with report_run("owner_tests") as report:
        report.update(run())
    print("PASS: owner source, identity and status checks.")
