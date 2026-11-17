"""Source connections, paths and run evidence for the individual implementation."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import html
import json
import msvcrt
import os
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/current"
ORIGINALS = ROOT / "data/original"
REPORTS = ROOT / "reports"
DATABASE = os.getenv("MONGO_DATABASE", "dmi_79189_v2")
INDEX = os.getenv("ES_REVIEW_INDEX", "dmi-79189-v2-reviews")
PEOPLE_INDEX = os.getenv("ES_PEOPLE_INDEX", "dmi-79189-v2-people")
ES_URL = os.getenv("ES_URL", "http://127.0.0.1:9200").rstrip("/")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
COUNTRIES = [
    ("GB", "United Kingdom", 22, "44", "7", 10),
    ("FR", "France", 14, "33", "6", 9),
    ("DE", "Germany", 12, "49", "151", 11),
    ("US", "United States", 11, "1", "212", 10),
    ("ES", "Spain", 8, "34", "6", 9),
    ("PT", "Portugal", 8, "351", "91", 9),
    ("NL", "Netherlands", 5, "31", "6", 9),
    ("IT", "Italy", 4, "39", "3", 10),
    ("BR", "Brazil", 4, "55", "119", 11),
    ("IE", "Ireland", 2, "353", "85", 9),
    ("BE", "Belgium", 2, "32", "4", 9),
    ("CN", "China", 2, "86", "13", 11),
    ("IN", "India", 2, "91", "9", 10),
    ("AO", "Angola", 1, "244", "92", 9),
    ("MA", "Morocco", 1, "212", "6", 9),
    ("ZA", "South Africa", 1, "27", "7", 9),
    ("JP", "Japan", 1, "81", "90", 10),
]
CONTRACT = {
    "model": "Qwen/Qwen3-Embedding-4B",
    "revision": "5cf2132abc99cad020ac570b19d031efec650f2b",
    "dimensions": 1024,
    "max_tokens": 8192,
    "pooling": "last_token",
    "normalization": "L2 after dimension truncation",
    "dtype": "bfloat16",
    "attention": "sdpa",
    "padding_side": "left",
    "text_processing": "HTML tags removed; entities decoded; whitespace collapsed",
    "query_instruction": "Given a travel accommodation search query, retrieve relevant guest reviews.",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_text(value):
    return re.sub(
        r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    ).strip()


def text_key(value):
    return hashlib.sha256(clean_text(value).encode()).hexdigest()


def mongo():
    from pymongo import MongoClient

    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tz_aware=True)


def es(method, path, body=None, lines=None):
    import requests

    response = requests.request(
        method,
        ES_URL + "/" + path,
        json=body,
        headers={
            "Content-Type": "application/x-ndjson" if lines else "application/json"
        },
        data=("\n".join(lines) + "\n").encode() if lines else None,
        timeout=180,
    )
    response.raise_for_status()
    result = response.json() if response.content else {}
    if isinstance(result, dict) and (
        result.get("errors")
        or result.get("timed_out")
        or result.get("_shards", {}).get("failed")
    ):
        raise RuntimeError("Incomplete Elasticsearch operation: " + str(result)[:500])
    return result


def scan(index, query=None, size=500, exclude_vectors=True):
    body = {"size": size, "sort": ["_doc"], "query": query or {"match_all": {}}}
    if exclude_vectors:
        body["_source"] = {"excludes": ["embedding"]}
    page = es("POST", index + "/_search?scroll=5m", body)
    cursor = page["_scroll_id"]
    try:
        while page["hits"]["hits"]:
            yield from page["hits"]["hits"]
            page = es("POST", "_search/scroll", {"scroll": "5m", "scroll_id": cursor})
            cursor = page["_scroll_id"]
    finally:
        es("DELETE", "_search/scroll", {"scroll_id": [cursor]})


def require_ready():
    metadata = next(iter(es("GET", INDEX + "/_mapping").values()))["mappings"].get(
        "_meta", {}
    )
    with mongo() as client:
        ready = client[DATABASE].state.find_one({"_id": "ingestion"})
    if not metadata.get("ingestion_complete") or not ready or not ready.get("ready"):
        raise RuntimeError("Load did not finish. Rerun ingest.py --reset.")
    if ready.get("quote_schema_version") != 1:
        raise RuntimeError("Price Quote model is not loaded. Rerun ingest.py --reset.")
    prepared = REPORTS / "preparation.json"
    if prepared.exists():
        manifest = read_json(prepared)
        if manifest.get("status") != "PASS":
            raise RuntimeError("Input preparation did not finish successfully.")
        if metadata.get("source_sha256") != manifest["sha256"]:
            raise RuntimeError("Prepared sources changed. Rerun ingest.py --reset.")
    if ready.get("source_sha256") != metadata.get("source_sha256"):
        raise RuntimeError("Source generations differ. Rerun ingest.py --reset.")
    return metadata


@contextmanager
def report_run(name):
    path = REPORTS / (name + ".json")
    report = {"status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat()}
    save_json(path, report)
    try:
        yield report
    except BaseException as error:
        report.update(
            status="INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "FAILED",
            error=str(error),
        )
        raise
    else:
        report["status"] = "PASS"
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_json(path, report)


@contextmanager
def writer_lock(name="writer.lock"):
    path = ROOT / ".runtime" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as f:
        f.write(b"0")
        f.flush()
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError("Another pipeline writer is running.") from error
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
