"""Add the Owner model in place without touching review text, vectors or inputs."""

from pymongo import UpdateMany
import argparse
import json
from owners import prepare, load_prepared, property_hosts, bson_owner
from support import (
    DATA,
    ROOT,
    REPORTS,
    PEOPLE_INDEX,
    DATABASE,
    checksum,
    es,
    mongo,
    read_json,
    save_json,
    require_ready,
    writer_lock,
)


def install(records, database):
    """Call only after all prepared owner identities and source references validate."""
    database.state.update_one(
        {"_id": "ingestion"}, {"$unset": {"owner_schema_version": ""}}
    )
    validator = read_json(ROOT / "database/owners_validator.json")
    if "owners" not in database.list_collection_names():
        database.create_collection("owners", validator=validator)
    else:
        database.command(
            "collMod", "owners", validator=validator, validationLevel="strict"
        )
    for field in ("owner_id", "person_id", "document_key"):
        database.owners.create_index(field, unique=True)
    for d in records:
        database.owners.replace_one({"_id": d["_id"]}, bson_owner(d), upsert=True)
    if database.owners.count_documents({}) != len(records):
        raise ValueError("Unexpected owners remain in the target collection")
    # Moderate validation permits the existing generation to gain its required link.
    database.command(
        "collMod",
        "accommodation",
        validator=read_json(ROOT / "database/accommodation_validator.json"),
        validationLevel="moderate",
    )
    updates = [
        UpdateMany(
            {"host_person_id": o["person_id"]}, {"$set": {"owner_id": o["owner_id"]}}
        )
        for o in records
    ]
    try:
        for start in range(0, len(updates), 500):
            database.accommodation.bulk_write(updates[start : start + 500])
    finally:
        database.command("collMod", "accommodation", validationLevel="strict")
    database.accommodation.create_index("owner_id")
    fields = read_json(ROOT / "database/people.json")["mappings"]["properties"]
    es(
        "PUT",
        PEOPLE_INDEX + "/_mapping",
        {"properties": {k: fields[k] for k in ("owner_id", "identity_document")}},
    )
    for start in range(0, len(records), 500):
        lines = []
        for o in records[start : start + 500]:
            lines.extend(
                [
                    json.dumps(
                        {"update": {"_index": PEOPLE_INDEX, "_id": o["person_id"]}}
                    ),
                    json.dumps(
                        {
                            "doc": {
                                "owner_id": o["owner_id"],
                                "identity_document": o["identity_document"],
                            }
                        }
                    ),
                ]
            )
        es("POST", "_bulk", lines=lines)
    es("POST", PEOPLE_INDEX + "/_refresh")
    database.state.update_one(
        {"_id": "ingestion"},
        {
            "$set": {
                "owner_schema_version": 1,
                "owner_input_sha256": checksum(DATA / "owners.json"),
            }
        },
    )


def run(prepare_input=False):
    metadata = require_ready()
    before = {name: checksum(DATA / name) for name in ("79189_1.csv", "79189_2.json")}
    if before != metadata["source_sha256"]:
        raise ValueError("Prepared inputs differ from the loaded generation")
    if prepare_input:
        prepare()
    records = load_prepared()
    hosts = property_hosts(read_json(DATA / "79189_2.json"))
    if before != {name: checksum(DATA / name) for name in before}:
        raise ValueError("Inputs changed during owner preparation")
    with mongo() as client:
        db = client[DATABASE]
        stored_hosts = {
            p["listing_id"]: p["host_person_id"]
            for p in db.accommodation.find({}, {"listing_id": 1, "host_person_id": 1})
        }
        if hosts != stored_hosts:
            raise ValueError("Prepared and stored accommodation ownership differs")
        if {o["person_id"] for o in records} != set(
            p["person_id"] for p in db.people.find({}, {"person_id": 1})
        ):
            raise ValueError("Prepared and stored host accounts differ")
        install(records, db)
    result = {
        "status": "PASS",
        "owners": len(records),
        "source_sha256": before,
        "review_index_rebuilt": False,
    }
    save_json(REPORTS / "owners_alignment.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Generate owner input from unchanged prepared sources first.",
    )
    args = parser.parse_args()
    with writer_lock():
        print(json.dumps(run(args.prepare), indent=2))
