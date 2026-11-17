"""Explicit validation and conservative reconciliation of source observations."""

from datetime import datetime
from copy import deepcopy
import json
import math
import re
from support import COUNTRIES, clean_text


def date_value(value, instant=False):
    if not isinstance(value, str) or not value.strip():
        return None
    formats = ["%Y-%m-%dT%H:%M:%SZ"] if instant else ["%Y-%m-%d", "%d/%m/%Y"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.strftime(fmt) != value or not 2000 <= parsed.year <= 2027:
                continue
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ" if instant else "%Y-%m-%d")
        except ValueError:
            pass
    return None


def phone_value(value, country=None):
    if not isinstance(value, str) or not value:
        return None
    if country is not None:
        match = next(
            (
                c
                for c in COUNTRIES
                if str(country).casefold() in (c[0].casefold(), c[1].casefold())
            ),
            None,
        )
        if match is None or not re.fullmatch(r"[0-9 -]+", value):
            return None
        digits = re.sub(r"\D", "", value)
        return "+" + match[3] + " " + digits if len(digits) == match[5] else None
    if not re.fullmatch(r"(?:\+|00)[0-9 -]+", value):
        return None
    digits = re.sub(r"\D", "", value[2:] if value.startswith("00") else value[1:])
    for c in sorted(COUNTRIES, key=lambda c: -len(c[3])):
        if digits.startswith(c[3]) and len(digits) == len(c[3]) + c[5]:
            return "+" + c[3] + " " + digits[len(c[3]) :]
    return None


def person_id(account):
    import hashlib

    return "P" + hashlib.sha256(("airbnb:" + str(account)).encode()).hexdigest()[:24]


def normalize(raw, kind):
    flags = []
    person = raw.get("person_id") if kind in ("person", "review") else raw.get("host_person_id")
    if not isinstance(person, str) or not re.fullmatch(r"P[0-9a-f]{24}", person):
        raise ValueError("Unusable person identity/reference")
    if kind != "person" and not raw.get("record_id"):
        raise ValueError("Missing observation identity")
    if kind == "review" and not re.fullmatch(r"R[0-9]+-[0-9]+", str(raw.get("review_id", ""))):
        raise ValueError("Unusable review identity")

    def check(field, value, converted, required=False):
        if value in (None, "", []):
            if required:
                flags.append("missing_" + field)
        elif converted is None:
            flags.append("invalid_" + field)
        elif converted != value:
            flags.append("normalized_" + field)
        return converted

    observed = check(
        "observed_at", raw.get("observed_at"), date_value(raw.get("observed_at"), True), True
    )
    if kind == "person":
        name = raw.get("name")
        name = name.strip() if isinstance(name, str) and name.strip() else None
        if name is None and raw.get("role") == "reviewer":
            flags.append("missing_name")
        value = raw.get("phone")
        country = raw.get("country")
        phone = check("phone", value, phone_value(value, country), True)
        return {
            "person_id": raw["person_id"],
            "name": name,
            "phone": phone,
            "observed_at": observed,
        }, flags
    d = deepcopy(raw)
    d["observed_at"] = observed
    if kind == "review":
        key = str(raw.get("listing_id", "")).removeprefix("LIS-")
        if not key.isdigit() or not re.fullmatch(r"P[0-9a-f]{24}", raw.get("person_id", "")):
            raise ValueError("Unusable review identity/reference")
        if raw["review_id"].split("-", 1)[0] != "R" + key:
            raise ValueError("Review identity disagrees with its property reference")
        d["listing_id"] = check("listing_id", raw["listing_id"], key)
        d["date"] = check("date", raw.get("date"), date_value(raw.get("date")), True)
        d["comments"] = raw.get("comments") or None
        if d["comments"] is None:
            flags.append("missing_comments")
        score = raw.get("review_score")
        try:
            score = float(score) if score not in (None, "") else None
        except (TypeError, ValueError):
            score = None
        if score is not None and (not math.isfinite(score) or not 0 <= score <= 5):
            score = None
        d["review_score"] = score
        if raw.get("review_score") in (None, ""):
            flags.append("missing_review_score")
        elif score is None:
            flags.append("invalid_review_score")
        d.pop("reviewer_name", None)
        d.pop("reviewer_phone", None)
    else:
        if not str(raw.get("listing_id", "")).isdigit():
            raise ValueError("Unusable property identity")
        loc = d["location"]
        lat, lon = loc.get("latitude"), loc.get("longitude")
        valid = all(
            isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
            for x in (lat, lon)
        )
        if not valid or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            loc["latitude"] = loc["longitude"] = None
            flags.append(
                "invalid_coordinates"
                if lat is not None or lon is not None
                else "missing_coordinates"
            )
        d["position"] = (
            [loc["longitude"], loc["latitude"]] if loc["latitude"] is not None else None
        )
        loc.pop("latitude", None)
        loc.pop("longitude", None)
        if loc["municipality"] == "Lisbon":
            loc["municipality"] = "Lisboa"
            flags.append("normalized_municipality")
        d.pop("price_quotes")
        scale = d["ratings"].pop("scale", 5)
        if scale not in (5, 100):
            raise ValueError("Undeclared rating scale")
        for field, value in d["ratings"].items():
            normalized = (
                value * 5 / scale
                if isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and 0 <= value <= scale
                else None
            )
            d["ratings"][field] = normalized
            if value is not None and normalized is None:
                flags.append("invalid_rating")
        if scale == 100:
            flags.append("normalized_rating_scale")
        aliases = {"wi-fi": "Wifi", "wireless internet": "Wifi"}
        amenities = d.get("amenities")
        d["amenities"] = (
            list(dict.fromkeys(aliases.get(a.casefold(), a) for a in amenities))
            if isinstance(amenities, list)
            else []
        )
        if amenities is None:
            flags.append("missing_amenities")
        if amenities is not None and d["amenities"] != amenities:
            flags.append("normalized_amenities")
        for field in ("first_date", "last_date"):
            d["review_summary"][field] = check(
                field,
                d["review_summary"].get(field),
                date_value(d["review_summary"].get(field)),
            )
        d["last_scraped"] = check(
            "last_scraped", d.get("last_scraped"), date_value(d.get("last_scraped")), True
        )
        for field in ("host_name", "host_phone", "host_phone_country"):
            d.pop(field, None)
    return d, sorted(set(flags))


def resolve(observations, keys):
    """Choose only ordered or agreeing values; unknown chronology never wins a conflict."""
    result = {}
    flags = set()
    decisions = {}
    for field in keys:
        available = [o for o in observations if o["values"].get(field) is not None]
        unique = {
            json.dumps(o["values"][field], sort_keys=True, ensure_ascii=False)
            for o in available
        }
        if not unique:
            result[field] = None
            continue
        if len(unique) == 1:
            selected = available[0]
            policy = "agreement"
        else:
            flags.add("changed_" + field)
            latest = max(
                (o["values"]["observed_at"] for o in available if o["values"]["observed_at"]),
                default=None,
            )
            dated = [o for o in available if o["values"]["observed_at"] == latest]
            values = {
                json.dumps(o["values"][field], sort_keys=True, ensure_ascii=False)
                for o in dated
            }
            if any(o["values"]["observed_at"] is None for o in available) or len(values) != 1:
                result[field] = None
                flags.add("unresolved_" + field)
                decisions[field] = {"rule": "unresolved chronology"}
                continue
            selected = dated[0]
            policy = "latest valid observation"
        result[field] = selected["values"][field]
        if len(unique) > 1:
            decisions[field] = {"rule": policy, "record_id": selected["record_id"]}
    fingerprints = set()
    versions = []
    for o in observations:
        flags.update(o["flags"])
        signature = json.dumps(o["raw"], sort_keys=True, ensure_ascii=False)
        if signature in fingerprints:
            flags.add("exact_duplicate_observation")
            next(v for v in versions if v["raw"] == o["raw"])["occurrences"] += 1
        else:
            fingerprints.add(signature)
            versions.append(
                {
                    "record_id": o["record_id"],
                    "observed_at": o["values"]["observed_at"],
                    "raw": o["raw"],
                    "flags": o["flags"],
                    "occurrences": 1,
                }
            )
    if len(versions) > 1:
        flags.add("multiple_observations")
    text = [
        clean_text(o["values"].get("comments"))
        for o in observations
        if o["values"].get("comments")
    ]
    if len(set(text)) > 1 and any(
        a.startswith(b) or b.startswith(a) for a in text for b in text if a != b
    ):
        flags.add("truncated_text_candidate")
    result["quality_flags"] = sorted(flags)
    result["resolution"] = decisions
    result["observations"] = versions
    result["observed_at"] = max(
        (o["values"]["observed_at"] for o in observations if o["values"]["observed_at"]),
        default=None,
    )
    return result
