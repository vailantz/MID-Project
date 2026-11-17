"""Price-quote observations and explicit retrieval-time reconciliation policies."""

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
import hashlib
import json
from bson import Decimal128
from rules import date_value

BASES = ("unspecified", "per_night", "per_stay")
CURRENCIES = ("EUR", "GBP", "USD")
FACTS = ("amount", "currency", "checkin", "checkout", "price_basis", "fees_included")
POLICIES = ("latest-valid", "agreement-only")
DEMO_QUOTES = 1000


def source_quote(listing_id, price, observed_at):
    if all(value is None for value in price.values()):
        return []
    return [
        {
            "quote_id": "Q" + listing_id + "-source",
            "listing_id": listing_id,
            "origin": "prepared_source",
            "amount": price.get("amount"),
            "currency": price.get("currency"),
            "checkin": price.get("quote_checkin"),
            "checkout": price.get("quote_checkout"),
            "observed_at": observed_at,
            "price_basis": "unspecified",
            "fees_included": None,
        }
    ]


def simulated_quotes(property, rng):
    """Create a small labelled scenario without assigning a preferred observation."""
    price = property["reference_price"]
    start = date_value(price.get("quote_checkin")) or "2026-11-01"
    checkin = datetime.strptime(start, "%Y-%m-%d") + timedelta(days=30)
    checkout = checkin + timedelta(days=3)
    base = price.get("amount") or 100
    factors = rng.sample([Decimal("0.9"), Decimal("1.1")], 2)
    rows = []
    for day, factor in zip((3, 5), factors):
        rows.append(
            {
                "quote_id": "Q" + property["listing_id"] + "-demo",
                "listing_id": property["listing_id"],
                "origin": "simulated",
                "amount": str((Decimal(str(base)) * factor).quantize(Decimal("0.01"))),
                "currency": "EUR",
                "checkin": checkin.strftime("%Y-%m-%d"),
                "checkout": checkout.strftime("%Y-%m-%d"),
                "observed_at": f"2026-10-{day:02}T12:00:00Z",
                "price_basis": "per_night",
                "fees_included": None,
            }
        )
    issues = Counter()
    if rng.random() < 0.05:
        count = rng.choices([1, 2, 3], [80, 17, 3])[0]
        for field in rng.sample(
            ["amount", "currency", "period", "observed_at", "duplicate"], count
        ):
            target = rng.choice(rows)
            if field == "amount":
                target[field] = rng.choice([None, "-10"])
            elif field == "currency":
                target[field] = rng.choice([None, "EURO"])
            elif field == "period":
                target["checkin"] = rng.choice([None, "1019-01-01", "not-a-date"])
            elif field == "observed_at":
                target[field] = rng.choice([None, "1019-10-01T12:00:00Z", "not-a-date"])
            else:
                copy = deepcopy(target)
                if rng.random() < 0.5:
                    copy["amount"] = "1.00" if target["amount"] != "1.00" else "2.00"
                rows.append(copy)
            issues[field] += 1
    rng.shuffle(rows)
    return rows, issues


def observation(raw):
    values = {}
    flags = []
    amount = raw.get("amount")
    try:
        number = (
            Decimal(str(amount))
            if amount is not None and not isinstance(amount, bool)
            else None
        )
        values["amount"] = (
            Decimal128(number)
            if number is not None and number.is_finite() and number >= 0
            else None
        )
    except (DecimalException, ValueError, TypeError):
        values["amount"] = None
    if values["amount"] is None:
        flags.append("missing_amount" if amount is None else "invalid_amount")
    for name, allowed in (("currency", CURRENCIES), ("price_basis", BASES)):
        value = raw.get(name)
        values[name] = value if value in allowed else None
        if values[name] is None:
            flags.append(("missing_" if value is None else "invalid_") + name)
    fees = raw.get("fees_included")
    values["fees_included"] = fees if isinstance(fees, bool) else None
    if fees is not None and not isinstance(fees, bool):
        flags.append("invalid_fees_included")
    for name in ("checkin", "checkout", "observed_at"):
        value = raw.get(name)
        converted = date_value(value, instant=name == "observed_at")
        values[name] = (
            datetime.fromisoformat(converted.replace("Z", "+00:00")).replace(
                tzinfo=timezone.utc
            )
            if converted
            else None
        )
        if converted is None:
            flags.append(("missing_" if value in (None, "") else "invalid_") + name)
    if values["checkin"] and values["checkout"] and values["checkin"] >= values["checkout"]:
        values["checkin"] = values["checkout"] = None
        flags.append("invalid_period")
    signature = json.dumps(raw, sort_keys=True, ensure_ascii=False)
    return {
        "observation_id": "O" + hashlib.sha256(signature.encode()).hexdigest()[:24],
        "raw": deepcopy(raw),
        "values": values,
        "quality_flags": sorted(flags),
    }


def documents(property_observations, listing_id):
    families = {}
    for record in property_observations:
        for raw in record["raw"]["price_quotes"]:
            key = raw["quote_id"]
            if raw["listing_id"] != listing_id or key not in (
                "Q" + listing_id + "-source",
                "Q" + listing_id + "-demo",
            ):
                raise ValueError("Conflicting price-quote identity/reference")
            if raw["origin"] not in ("prepared_source", "simulated"):
                raise ValueError("Unknown quote origin")
            expected_origin = "prepared_source" if key.endswith("-source") else "simulated"
            if raw["origin"] != expected_origin:
                raise ValueError("Quote identity and origin disagree")
            family = families.setdefault(
                key,
                {
                    "_id": key,
                    "quote_id": key,
                    "listing_id": listing_id,
                    "origin": raw["origin"],
                    "observations": [],
                },
            )
            if family["origin"] != raw["origin"]:
                raise ValueError("Conflicting quote origin")
            family["observations"].append(observation(raw))
    return list(families.values())


def select_quote(document, policy="latest-valid"):
    """Resolve an atomic price/context tuple without modifying the stored history."""
    if policy not in POLICIES:
        raise ValueError("Unknown quote policy")
    result = {k: document[k] for k in ("quote_id", "listing_id", "origin")}
    result.update(
        policy=policy,
        status="unavailable",
        price=None,
        observed_at=None,
        observation_ids=[],
        reason="No usable monetary observation",
    )
    usable = [
        o
        for o in document["observations"]
        if o["values"]["amount"] is not None
        and o["values"]["currency"] in CURRENCIES
        and o["values"]["price_basis"] in BASES
    ]
    if not usable:
        return result

    def key(o):
        return tuple(
            (
                o["values"][k].to_decimal()
                if isinstance(o["values"][k], Decimal128)
                else o["values"][k]
            )
            for k in FACTS
        )

    if len({key(o) for o in usable}) == 1:
        chosen, reason = usable, "All usable observations agree"
    elif policy == "agreement-only":
        result.update(status="unresolved", reason="Observations disagree")
        return result
    elif any(o["values"]["observed_at"] is None for o in usable):
        result.update(status="unresolved", reason="Conflicting values with unknown chronology")
        return result
    else:
        latest = max(o["values"]["observed_at"] for o in usable)
        chosen = [o for o in usable if o["values"]["observed_at"] == latest]
        if len({key(o) for o in chosen}) != 1:
            result.update(status="unresolved", reason="Latest observations disagree")
            return result
        reason = "Latest usable observations agree"
    result.update(
        status="resolved",
        price={k: chosen[0]["values"][k] for k in FACTS},
        observed_at=max(
            (o["values"]["observed_at"] for o in chosen if o["values"]["observed_at"]),
            default=None,
        ),
        observation_ids=sorted({o["observation_id"] for o in chosen}),
        reason=reason,
    )
    return result


def eligible_properties(database, policy="latest-valid"):
    filters = {
        "location.municipality": "Lisboa",
        "capacity": {"$gte": 2},
        "amenities": "Wifi",
        "ratings.rating": {"$gte": 4.8},
    }
    properties = {d["listing_id"]: d for d in database.accommodation.find(filters)}
    result = []
    for document in database.price_quotes.find(
        {"listing_id": {"$in": list(properties)}, "origin": "prepared_source"}
    ):
        decision = select_quote(document, policy)
        price = decision["price"]
        if (
            price
            and price["currency"] == "EUR"
            and price["price_basis"] == "unspecified"
            and price["amount"].to_decimal() <= 150
        ):
            result.append({"property": properties[document["listing_id"]], "quote": decision})
    return sorted(
        result,
        key=lambda r: (r["quote"]["price"]["amount"].to_decimal(), r["property"]["listing_id"]),
    )


def read_quotes(database, listing_id, policy="latest-valid", checkin=None, checkout=None):
    if (checkin is None) != (checkout is None):
        raise ValueError("Supply both requested stay dates")
    if checkin is not None:
        if (
            date_value(checkin) != checkin
            or date_value(checkout) != checkout
            or checkin >= checkout
        ):
            raise ValueError("Use a valid YYYY-MM-DD stay interval")
    result = []
    for document in database.price_quotes.find({"listing_id": listing_id}):
        decision = select_quote(document, policy)
        price = decision["price"]
        if checkin is not None and (
            not price
            or not price["checkin"]
            or not price["checkout"]
            or price["checkin"].strftime("%Y-%m-%d") != checkin
            or price["checkout"].strftime("%Y-%m-%d") != checkout
        ):
            continue
        result.append({**decision, "observations": document["observations"]})
    return sorted(result, key=lambda q: q["quote_id"])
