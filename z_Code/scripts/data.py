"""Build the two sources with reproducible, approximately five-percent quality cases."""

from collections import Counter
from copy import deepcopy
import argparse
import csv
import os
import random
from support import (
    COUNTRIES,
    DATA,
    ORIGINALS,
    checksum,
    read_json,
    report_run,
    save_json,
    writer_lock,
)
from rules import person_id
from quotes import DEMO_QUOTES, simulated_quotes, source_quote

FIELDS = [
    "review_id",
    "record_id",
    "listing_id",
    "person_id",
    "date",
    "observed_at",
    "reviewer_name",
    "reviewer_phone",
    "comments",
    "review_score",
]
BASE_TIME = "2026-10-01T12:00:00Z"
NEW_TIME = "2026-10-02T12:00:00Z"
RATE = 0.05


def build(limit=None):
    phones_rng = random.Random(42)
    quality_rng = random.Random(43)
    score_rng = random.Random(44)
    quote_rng = random.Random(45)
    properties = read_json(ORIGINALS / "79189_2.json")
    hosts = {str(d["host_id"]) for d in properties}
    accounts = {}
    used = set()
    available = []
    country_counts = Counter()
    shared = 0

    def contact(account):
        nonlocal shared
        account = str(account)
        if account not in accounts:
            if (len(accounts) + 1) % 2000 == 0:
                chosen = available.pop(phones_rng.randrange(len(available)))
                accounts[account] = chosen
                shared += 2
            else:
                weights = (
                    [70 if c[0] == "PT" else c[2] * 30 / 92 for c in COUNTRIES]
                    if account in hosts
                    else [c[2] for c in COUNTRIES]
                )
                country = phones_rng.choices(COUNTRIES, weights)[0]
                while True:
                    digits = country[4] + "".join(
                        str(phones_rng.randrange(10))
                        for _ in range(country[5] - len(country[4]))
                    )
                    phone = "+" + country[3] + " " + digits
                    if phone not in used and not (
                        country[0] == "US" and digits[3] in "01"
                    ):
                        break
                used.add(phone)
                accounts[account] = (phone, country[1])
                available.append(accounts[account])
                country_counts[country[0]] += 1
        return accounts[account]

    counts = Counter()
    multiplicity = {"review": Counter(), "property": Counter()}
    examples = {}

    def mutations(d, kind):
        original = deepcopy(d)
        groups = (
            [
                "phone",
                "date",
                "observed_at",
                "duplicate",
                "name",
                "text",
                "score",
                "listing_format",
            ]
            if kind == "review"
            else [
                "phone",
                "observed_at",
                "duplicate",
                "price",
                "coordinates",
                "rating",
                "amenities",
                "last_scraped",
            ]
        )
        selected = (
            quality_rng.sample(groups, quality_rng.choices([1, 2, 3], [80, 17, 3])[0])
            if quality_rng.random() < RATE
            else []
        )
        if selected:
            multiplicity[kind][str(len(selected))] += 1
        records = [d]
        for group in selected:
            variant = ""
            if group == "phone":
                field = "reviewer_phone" if kind == "review" else "host_phone"
                variant = quality_rng.choice(["missing", "short", "country", "format"])
                if variant == "missing":
                    d[field] = None
                elif variant == "short":
                    d[field] = "12345" if kind == "property" else "+351 12345"
                elif variant == "country":
                    if kind == "review":
                        d[field] = "+999 " + d[field].split(" ")[1]
                    else:
                        d["host_phone_country"] = "Unknown"
                elif kind == "review":
                    d[field] = d[field].replace("+", "00", 1)
                else:
                    d[field] = d[field][:3] + " " + d[field][3:]
            elif group in ("date", "last_scraped", "observed_at"):
                variant = quality_rng.choice(["missing", "format", "year"])
                value = d[group]
                d[group] = (
                    None
                    if variant == "missing"
                    else "not-a-date" if variant == "format" else "1019" + value[4:]
                )
            elif group == "name":
                d["reviewer_name"] = None
            elif group == "text":
                d["comments"] = None
            elif group == "score":
                d["review_score"] = None if quality_rng.random() < 0.7 else 9
            elif group == "listing_format":
                d["listing_id"] = "LIS-" + d["listing_id"]
            elif group == "price":
                d["reference_price"]["amount"] = (
                    None
                    if d["reference_price"]["amount"] is not None
                    and quality_rng.random() < 0.7
                    else -10
                )
            elif group == "coordinates":
                variant = quality_rng.choice(["missing", "range"])
                if variant == "missing":
                    d["location"]["latitude"] = d["location"]["longitude"] = None
                else:
                    d["location"]["latitude"] = 999
            elif group == "rating":
                variant = quality_rng.choice(["missing", "range", "scale"])
                if variant == "missing":
                    d["ratings"]["rating"] = None
                elif variant == "range":
                    d["ratings"]["rating"] = 9
                else:
                    d["ratings"] = {
                        k: (v * 20 if v is not None else None)
                        for k, v in d["ratings"].items()
                        if k != "scale"
                    }
                    d["ratings"]["scale"] = 100
            elif group == "amenities":
                d["amenities"] = None
            elif group == "duplicate":
                continue
            key = kind + ":" + group + (":" + variant if variant else "")
            counts[key] += 1
            examples.setdefault(
                key,
                {"entity_id": d["review_id"] if kind == "review" else d["listing_id"]},
            )
        if "duplicate" in selected:
            variants = (
                ["exact", "cutoff", "score"]
                if kind == "review"
                else ["exact", "coordinates", "rating"]
            )
            variant = quality_rng.choice(variants)
            copy = deepcopy(d)
            if variant != "exact":
                copy["record_id"] = d["record_id"] + ":revision"
                copy["observed_at"] = NEW_TIME
                if variant == "cutoff":
                    full = original["comments"] or ""
                    d["comments"] = full[: max(1, len(full) // 2)]
                    copy["comments"] = full
                elif variant == "score":
                    copy["review_score"] = 1 if d["review_score"] == 5 else 5
                elif variant == "coordinates":
                    copy["location"]["latitude"] = (
                        original["location"]["latitude"] + 0.0006
                        if original["location"]["latitude"] is not None
                        else None
                    )
                    copy["location"]["longitude"] = (
                        original["location"]["longitude"] + 0.0006
                        if original["location"]["longitude"] is not None
                        else None
                    )
                else:
                    scale = copy["ratings"].get("scale", 5)
                    copy["ratings"]["rating"] = scale * 0.8
            records.append(copy)
            key = kind + ":duplicate:" + variant
            counts[key] += 1
            examples.setdefault(
                key,
                {"entity_id": d["review_id"] if kind == "review" else d["listing_id"]},
            )
        return records, bool(selected)

    DATA.mkdir(parents=True, exist_ok=True)
    review_new = DATA / "79189_1.new.csv"
    n = 0
    affected = 0
    observations = 0
    with (ORIGINALS / "79189_1.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source, review_new.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        for row in csv.DictReader(source):
            if limit is not None and n >= limit:
                break
            phone, _ = contact(row["reviewer_id"])
            rid = "R" + row["listing_id"] + "-" + row["id"]
            d = {
                "review_id": rid,
                "record_id": rid + ":snapshot",
                "listing_id": row["listing_id"],
                "person_id": person_id(row["reviewer_id"]),
                "date": row["date"],
                "observed_at": BASE_TIME,
                "reviewer_name": row["reviewer_name"],
                "reviewer_phone": phone,
                "comments": row["comments"],
                "review_score": score_rng.choices([1, 2, 3, 4, 5], [1, 2, 7, 25, 65])[
                    0
                ],
            }
            records, changed = mutations(d, "review")
            writer.writerows(records)
            n += 1
            affected += changed
            observations += len(records)
            if n % 250000 == 0:
                print(f"Prepared {n:,} original reviews.", flush=True)
    result = []
    affected_properties = 0
    quote_ids = set()
    quote_observations = 0
    quote_issues = Counter()
    affected_quotes = 0
    for index, raw in enumerate(properties):
        phone, country = contact(raw["host_id"])
        d = deepcopy(raw)
        for field in ("host_id", "listing_url", "license"):
            d.pop(field, None)
        d.update(
            record_id=d["listing_id"] + ":snapshot",
            host_person_id=person_id(raw["host_id"]),
            host_name=None,
            host_phone=phone.split(" ")[1],
            host_phone_country=country,
            observed_at=BASE_TIME,
        )
        d["ratings"]["scale"] = 5
        records, changed = mutations(d, "property")
        demo, issues = (
            simulated_quotes(raw, quote_rng) if index < DEMO_QUOTES else ([], {})
        )
        quote_issues.update(issues)
        affected_quotes += bool(issues)
        for record in records:
            price = record.pop("reference_price")
            record["price_quotes"] = source_quote(
                record["listing_id"], price, record["observed_at"]
            ) + deepcopy(demo)
            quote_ids.update(q["quote_id"] for q in record["price_quotes"])
            quote_observations += len(record["price_quotes"])
        result.extend(records)
        affected_properties += changed
    property_new = DATA / "79189_2.new.json"
    save_json(property_new, result)
    os.replace(review_new, DATA / "79189_1.csv")
    os.replace(property_new, DATA / "79189_2.json")
    manifest = {
        "seed": {"phones": 42, "quality": 43, "scores": 44},
        "target_rate": RATE,
        "logical_reviews": n,
        "logical_properties": len(properties),
        "review_observations": observations,
        "property_observations": len(result),
        "affected_reviews": affected,
        "affected_properties": affected_properties,
        "review_rate": affected / n,
        "property_rate": affected_properties / len(properties),
        "issue_multiplicity": {k: dict(v) for k, v in multiplicity.items()},
        "injections": dict(counts),
        "examples": examples,
        "person_accounts": len(accounts),
        "price_quotes": {
            "logical_quotes": len(quote_ids),
            "simulated_quotes": min(DEMO_QUOTES, len(properties)),
            "observations": quote_observations,
            "affected_simulated_quotes": affected_quotes,
            "simulated_injections": dict(quote_issues),
            "seed": 45,
        },
        "shared_phone_accounts": shared,
        "country_counts": dict(country_counts),
        "generated_fields": [
            "phone contacts",
            "review_score",
            "observation timestamps",
            "revised observations",
            "simulated price-quote histories and their billing units",
        ],
        "source_sha256": {
            p.name: checksum(p)
            for p in ORIGINALS.glob("*")
            if p.suffix in (".csv", ".json")
        },
        "sha256": {
            name: checksum(DATA / name) for name in ("79189_1.csv", "79189_2.json")
        },
    }
    print(
        f"Affected families: reviews {manifest['review_rate']:.2%}; properties {manifest['property_rate']:.2%}.",
        flush=True,
    )
    from owners import prepare

    prepare()
    manifest["owners_sha256"] = checksum(DATA / "owners.json")
    manifest["generated_fields"].extend(
        ["owner identification documents", "dated owner activity and document states"]
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional small review sample for installation checks.",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    with writer_lock(), report_run("preparation") as report:
        report.update(build(args.limit))
