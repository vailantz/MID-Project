"""Resume Qwen embedding generation or run a semantic review search."""

import argparse
import json
import time

from support import (
    CONTRACT,
    DATA,
    INDEX,
    checksum,
    clean_text,
    es,
    report_run,
    scan,
    writer_lock,
    require_ready,
)

WINDOW_SIZE = 1024
BULK_SIZE = 128


def mapping():
    return next(iter(es("GET", INDEX + "/_mapping").values()))["mappings"]


def check_model():
    metadata = require_ready()
    if not metadata.get("ingestion_complete"):
        raise RuntimeError("Ingestion has not completed. Reload before running NLP.")
    if metadata.get("embedding_contract") != CONTRACT:
        raise RuntimeError("Index embeddings do not match the configured Qwen model.")


def write_vectors(records, vectors):
    for start in range(0, len(records), BULK_SIZE):
        lines = []
        for (key, _), vector in zip(
            records[start : start + BULK_SIZE], vectors[start : start + BULK_SIZE]
        ):
            lines.extend(
                [
                    json.dumps({"update": {"_index": INDEX, "_id": key}}),
                    json.dumps(
                        {"doc": {"embedding": vector.tolist(), "embedding_status": "ready"}}
                    ),
                ]
            )
        es("POST", "_bulk", lines=lines)


def embed(limit):
    from encoder import Encoder, CONTRACT as encoder_contract

    if encoder_contract != CONTRACT:
        raise RuntimeError("Encoder settings do not match index metadata.")
    check_model()
    if mapping()["_meta"]["sha256"] != checksum(DATA / "79189_1.csv"):
        raise RuntimeError("Input changed after ingestion; reload before running NLP.")
    encoder = None
    pending = scan(
        INDEX,
        {
            "bool": {
                "must_not": [
                    {"exists": {"field": "embedding"}},
                    {"term": {"embedding_status": "empty"}},
                ]
            }
        },
        size=WINDOW_SIZE,
    )
    processed, generated = 0, 0
    window = []
    start = time.monotonic()
    old_interval = next(iter(es("GET", INDEX + "/_settings").values()))["settings"][
        "index"
    ].get("refresh_interval", "1s")
    es("PUT", INDEX + "/_settings", {"index": {"refresh_interval": "30s"}})

    def process(hits):
        nonlocal encoder, generated
        records = [(h["_id"], clean_text(h["_source"]["comments"])) for h in hits]
        for key, text in records:
            if not text:
                es("POST", INDEX + "/_update/" + key, {"doc": {"embedding_status": "empty"}})
        records = [(key, text) for key, text in records if text]
        if records:
            encoder = encoder or Encoder()
            for positions in encoder.batches(records):
                batch = [records[i] for i in positions]
                write_vectors(batch, encoder.encode([text for _, text in batch]))
                generated += len(batch)

    try:
        for hit in pending:
            window.append(hit)
            processed += 1
            if len(window) == WINDOW_SIZE or processed == limit:
                process(window)
                window = []
                print(
                    f"{processed:,} pending reviews processed; {generated:,} vectors generated.",
                    flush=True,
                )
            if processed == limit:
                break
        if window:
            process(window)
    finally:
        pending.close()
        es("PUT", INDEX + "/_settings", {"index": {"refresh_interval": old_interval}})
        es("POST", INDEX + "/_refresh")
    report = {
        "processed_this_run": processed,
        "generated_this_run": generated,
        "seconds": round(time.monotonic() - start, 2),
        "total_reviews": es("GET", INDEX + "/_count")["count"],
        "reviews_with_vectors": es(
            "POST", INDEX + "/_count", {"query": {"exists": {"field": "embedding"}}}
        )["count"],
        "empty_reviews": es(
            "POST", INDEX + "/_count", {"query": {"term": {"embedding_status": "empty"}}}
        )["count"],
    }
    report["complete"] = (
        report["reviews_with_vectors"] + report["empty_reviews"] == report["total_reviews"]
    )
    print(json.dumps(report, indent=2), flush=True)
    report["source_sha256"] = mapping()["_meta"]["source_sha256"]
    return report


def search(text, k):
    from encoder import Encoder, CONTRACT as encoder_contract

    if encoder_contract != CONTRACT:
        raise RuntimeError("Query encoder settings do not match index metadata.")
    check_model()
    vector = Encoder().query(text)
    result = es(
        "POST",
        INDEX + "/_search",
        {
            "size": k,
            "_source": {"excludes": ["embedding"]},
            "knn": {
                "field": "embedding",
                "query_vector": vector.tolist(),
                "k": k,
                "num_candidates": max(100, k * 10),
            },
        },
    )
    return [{"review": h["_source"], "score": h["_score"]} for h in result["hits"]["hits"]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, help="Maximum pending reviews to process; omit for the full run."
    )
    parser.add_argument("--query", help="Search by meaning instead of generating embeddings.")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if not 1 <= args.k <= 100:
        parser.error("--k must be between 1 and 100")
    if args.query is not None:
        with report_run("semantic_search") as report:
            if not args.query.strip():
                parser.error("Query must not be empty")
            result = search(args.query, args.k)
            report.update(hits=result, source_sha256=mapping()["_meta"]["source_sha256"])
            print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        with writer_lock(), report_run("nlp") as report:
            report.update(embed(args.limit))
