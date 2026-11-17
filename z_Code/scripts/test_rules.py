"""Small fixed cases for validation, temporal conflicts and duplicate observations."""

from copy import deepcopy
import unittest
from rules import date_value, normalize, phone_value, resolve
from quotes import documents, select_quote
from owners import (
    cc_valid,
    calendar,
    generate,
    validate_document,
    validate_owners,
    document_status,
)


class OwnerRules(unittest.TestCase):
    def fixture(self, count=40):
        hosts = {str(i): "P" + f"{i:024x}" for i in range(count)}
        activity = {
            str(i): {
                "recent_review_count": int(i < count - 5),
                "latest_publication_date": (
                    "2026-09-01" if i < count - 5 else "2024-01-01"
                ),
            }
            for i in range(count)
        }
        return hosts, activity

    def test_owner_document_formats(self):
        self.assertTrue(cc_valid("000000000ZZ4"))
        self.assertFalse(cc_valid("000000000ZZ5"))
        hosts, activity = self.fixture()
        for owner in generate(hosts, activity):
            self.assertEqual(
                validate_document(owner["identity_document"]), owner["document_key"]
            )
        passport = {
            "issuing_country": "GB",
            "type": "PASSPORT",
            "number": "001234567",
            "nationality": "British",
            "expires_on": "2035-01-01",
            "is_synthetic": True,
        }
        self.assertTrue(validate_document(passport).endswith("001234567"))
        for number in [None, "12345", "12345678X"]:
            with self.assertRaises(ValueError):
                validate_document({**passport, "number": number})

    def test_owner_date_domain_and_inclusive_expiry(self):
        for value in ["1900-01-01", "2199-12-31"]:
            self.assertEqual(calendar(value).isoformat(), value)
        for value in ["1899-12-31", "2200-01-01", "2026-02-30"]:
            with self.assertRaises(ValueError):
                calendar(value)
        hosts, activity = self.fixture()
        owner = generate(hosts, activity)[0]
        owner["identity_document"]["expires_on"] = "2035-10-20"
        self.assertTrue(
            document_status(owner, "2035-10-20")["documentation_up_to_date"]
        )
        self.assertTrue(document_status(owner, "2035-10-21")["needs_renewal"])

    def test_owner_report_scenario_is_reproducible(self):
        hosts = {str(i): "P" + f"{i:024x}" for i in range(9484)}
        activity = {
            str(i): {
                "recent_review_count": int(i < 7820),
                "latest_publication_date": "2026-01-01" if i < 7820 else None,
            }
            for i in range(9484)
        }
        records = generate(hosts, activity)
        self.assertEqual(records, generate(hosts, activity))
        self.assertEqual(
            sum(o["identity_document"]["type"] == "CC" for o in records), 6693
        )
        self.assertEqual(sum(o["active"] and o["needs_renewal"] for o in records), 30)
        self.assertEqual(
            sum(not o["active"] and o["needs_renewal"] for o in records), 357
        )

    def test_owner_critical_documents_are_prevalidated(self):
        hosts, activity = self.fixture()
        records = generate(hosts, activity)
        for change in [
            lambda r: r[0].pop("identity_document"),
            lambda r: r[0]["identity_document"].update(number="bad"),
            lambda r: r[1].update(
                identity_document=deepcopy(r[0]["identity_document"]),
                document_key=r[0]["document_key"],
            ),
            lambda r: r.append(deepcopy(r[0])),
        ]:
            bad = deepcopy(records)
            change(bad)
            with self.assertRaises((ValueError, KeyError)):
                validate_owners(bad, hosts)

    def test_owner_activity_combines_multiple_properties(self):
        person = "P" + "1" * 24
        hosts = {"10": person, "20": person}
        activity = {
            "10": {"recent_review_count": 3, "latest_publication_date": "2026-01-01"},
            "20": {"recent_review_count": 2, "latest_publication_date": "2026-10-01"},
        }
        owner = generate(hosts, activity)[0]
        self.assertEqual(owner["activity"]["accommodation_count"], 2)
        self.assertEqual(owner["activity"]["recent_review_count"], 5)
        self.assertEqual(owner["activity"]["latest_publication_date"], "2026-10-01")
        self.assertTrue(owner["active"])

    def test_owner_queries_keep_activity_snapshot_and_original(self):
        hosts, activity = self.fixture()
        owner = generate(hosts, activity)[0]
        before = deepcopy(owner)
        result = document_status(owner, "2199-01-01")
        self.assertEqual(owner, before)
        self.assertEqual(result["activity"], owner["activity"])
        self.assertEqual(result["reference_dates"]["activity_as_of"], "2026-11-13")
        self.assertEqual(result["reference_dates"]["status_as_of"], "2199-01-01")

    def test_owner_inconsistent_states_are_rejected(self):
        hosts, activity = self.fixture()
        records = generate(hosts, activity)
        for field in ["active", "documentation_up_to_date", "needs_renewal"]:
            bad = deepcopy(records)
            bad[0][field] = not bad[0][field]
            with self.assertRaises(ValueError):
                validate_owners(bad, hosts)
        bad = deepcopy(records)
        bad[0]["active"] = False
        bad[0]["activity"]["recent_review_count"] = 0
        with self.assertRaises(ValueError):
            validate_owners(bad, hosts)


class QuoteRules(unittest.TestCase):
    def raw(self, amount="100", time="2026-10-01T12:00:00Z"):
        return {
            "quote_id": "Q1-demo",
            "listing_id": "1",
            "origin": "simulated",
            "amount": amount,
            "currency": "EUR",
            "price_basis": "per_night",
            "fees_included": None,
            "checkin": "2026-11-01",
            "checkout": "2026-11-04",
            "observed_at": time,
        }

    def document(self, *rows):
        return documents([{"raw": {"price_quotes": list(rows)}}], "1")[0]

    def test_price_policy_is_applied_without_changing_history(self):
        document = self.document(self.raw("120", "2026-10-02T12:00:00Z"), self.raw())
        before = deepcopy(document)
        selected = select_quote(document)
        self.assertEqual(selected["price"]["amount"].to_decimal(), 120)
        self.assertEqual(
            select_quote(document, "agreement-only")["status"], "unresolved"
        )
        self.assertEqual(document, before)
        self.assertNotIn("price", document)

    def test_price_unknown_date_and_tie_remain_unresolved(self):
        for time in (None, "2026-10-01T12:00:00Z"):
            d = self.document(self.raw(), self.raw("120", time))
            self.assertEqual(select_quote(d)["status"], "unresolved")

    def test_price_invalid_values_are_retained(self):
        bad = self.raw("-10", "1019-10-01T12:00:00Z")
        d = self.document(bad, self.raw())
        self.assertEqual(d["observations"][0]["raw"], bad)
        self.assertIsNone(d["observations"][0]["values"]["amount"])
        self.assertEqual(select_quote(d)["price"]["amount"].to_decimal(), 100)

    def test_price_exact_copies_are_both_retained(self):
        d = self.document(self.raw("100.00"), self.raw("100.00"))
        self.assertEqual(len(d["observations"]), 2)
        self.assertEqual(select_quote(d)["price"]["amount"].to_decimal(), 100)

    def test_price_currency_and_period_are_validated(self):
        bad = self.raw()
        bad.update(currency="EURO", checkin="2026-11-05")
        o = self.document(bad)["observations"][0]
        self.assertIn("invalid_currency", o["quality_flags"])
        self.assertIn("invalid_period", o["quality_flags"])
        self.assertEqual(select_quote(self.document(bad))["status"], "unavailable")

    def test_price_basis_is_not_inferred(self):
        raw = self.raw()
        raw["price_basis"] = "unspecified"
        self.assertEqual(
            select_quote(self.document(raw))["price"]["price_basis"], "unspecified"
        )


class QualityRules(unittest.TestCase):
    def test_missing_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize({"person_id": "", "review_id": "R1", "record_id": "r1"}, "review")
        with self.assertRaisesRegex(ValueError, "property reference"):
            normalize(
                {
                    "person_id": "P" + "1" * 24,
                    "review_id": "R10-123",
                    "record_id": "r1",
                    "listing_id": "20",
                },
                "review",
            )

    def observation(self, record, value, time):
        return {
            "record_id": record,
            "raw": {"value": value, "time": time},
            "values": {"score": value, "observed_at": time},
            "flags": [],
        }

    def test_dates_preserve_unknowns(self):
        self.assertEqual(date_value("02/01/2019"), "2019-01-02")
        for value in [None, "", "1019-01-01", "2019-02-30", "tomorrow", "9999-01-01"]:
            self.assertIsNone(date_value(value))

    def test_phone_formats_and_invalid_values(self):
        self.assertEqual(phone_value("00351912345678"), "+351 912345678")
        self.assertEqual(phone_value("912 345 678", "Portugal"), "+351 912345678")
        for value in ["+351 12345", "+999 912345678", "912345678", None]:
            self.assertIsNone(phone_value(value))
        self.assertIsNone(phone_value("912345678", "Unknown"))

    def test_newer_score(self):
        old = self.observation("old", 2, "2026-10-01T12:00:00Z")
        new = self.observation("new", 5, "2026-10-02T12:00:00Z")
        result = resolve([new, old], ["score"])
        self.assertEqual(result["score"], 5)
        self.assertEqual(result["resolution"]["score"]["record_id"], "new")

    def test_missing_time_does_not_win(self):
        old = self.observation("old", 2, "2026-10-01T12:00:00Z")
        unknown = self.observation("unknown", 5, None)
        result = resolve([old, unknown], ["score"])
        self.assertIsNone(result["score"])
        self.assertIn("unresolved_score", result["quality_flags"])

    def test_same_time_conflict(self):
        result = resolve(
            [
                self.observation("a", 2, "2026-10-01T12:00:00Z"),
                self.observation("b", 5, "2026-10-01T12:00:00Z"),
            ],
            ["score"],
        )
        self.assertIsNone(result["score"])

    def test_exact_duplicate_is_one_observation(self):
        original = self.observation("same", 4, "2026-10-01T12:00:00Z")
        result = resolve([original, deepcopy(original)], ["score"])
        self.assertEqual(result["score"], 4)
        self.assertEqual(len(result["observations"]), 1)
        self.assertEqual(result["observations"][0]["occurrences"], 2)

    def test_coordinate_pair_is_atomic(self):
        observations = []
        for key, pair, time in [
            ("a", [-9.1, 38.7], "2026-10-01T12:00:00Z"),
            ("b", [-9.2, 38.8], "2026-10-02T12:00:00Z"),
        ]:
            observations.append(
                {
                    "record_id": key,
                    "raw": {"position": pair},
                    "values": {"position": pair, "observed_at": time},
                    "flags": [],
                }
            )
        self.assertEqual(resolve(observations, ["position"])["position"], [-9.2, 38.8])
        observations[1]["values"]["observed_at"] = None
        self.assertIsNone(resolve(observations, ["position"])["position"])

    def test_truncated_comment(self):
        observations = []
        for key, text, time in [
            ("a", "Quiet and", "2026-10-01T12:00:00Z"),
            ("b", "Quiet and comfortable apartment.", "2026-10-02T12:00:00Z"),
        ]:
            observations.append(
                {
                    "record_id": key,
                    "raw": {"comments": text},
                    "values": {"comments": text, "observed_at": time},
                    "flags": [],
                }
            )
        result = resolve(observations, ["comments"])
        self.assertEqual(result["comments"], "Quiet and comfortable apartment.")
        self.assertIn("truncated_text_candidate", result["quality_flags"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
