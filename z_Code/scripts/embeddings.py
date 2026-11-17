"""Export or restore completed review vectors without running the language model."""

from concurrent.futures import ProcessPoolExecutor
from functools import partial

import argparse
import base64
import gzip
import json
import math
import struct
from pathlib import Path

from support import (
    ROOT,
    INDEX,
    CONTRACT,
    checksum,
    clean_text,
    text_key,
    es,
    scan,
    read_json,
    save_json,
    require_ready,
    writer_lock,
    report_run,
)

DIRECTORY = ROOT / "data/embeddings"
PARTITIONS = 32
BATCH_SIZE = 128
DIMENSIONS = CONTRACT["dimensions"]
VECTOR = struct.Struct("<" + "f" * DIMENSIONS)


def counts():
    total = es("GET", INDEX + "/_count")["count"]
    vectors = es(
        "POST", INDEX + "/_count", {"query": {"exists": {"field": "embedding"}}}
    )["count"]
    empty = es(
        "POST", INDEX + "/_count", {"query": {"term": {"embedding_status": "empty"}}}
    )["count"]
    return {"reviews": total, "vectors": vectors, "empty": empty}


def context():
    metadata = require_ready()
    if metadata["embedding_contract"] != CONTRACT:
        raise ValueError("The index uses another embedding model or configuration")
    return {"embedding_contract": CONTRACT, "source_sha256": metadata["source_sha256"]}


def checked_vector(encoded):
    values = VECTOR.unpack(base64.b64decode(encoded, validate=True))
    if (
        not all(math.isfinite(v) for v in values)
        or abs(sum(v * v for v in values) - 1) > 0.001
    ):
        raise ValueError("Invalid or non-normalized embedding")
    return values


def save_manifest(path, manifest):
    temporary = path.with_suffix(".tmp")
    save_json(temporary, manifest)
    temporary.replace(path)


def vector_slice(index, partitions, partition):
    """Independent scroll slices let completed parts survive an interrupted export."""
    page = es(
        "POST",
        index + "/_search?scroll=5m",
        {
            "size": 256,
            "sort": ["_doc"],
            "slice": {"id": partition, "max": partitions},
            "_source": ["embedding", "comments"],
            "query": {"exists": {"field": "embedding"}},
        },
    )
    cursor = page["_scroll_id"]
    try:
        while page["hits"]["hits"]:
            yield from page["hits"]["hits"]
            page = es("POST", "_search/scroll", {"scroll": "5m", "scroll_id": cursor})
            cursor = page["_scroll_id"]
    finally:
        es("DELETE", "_search/scroll", {"scroll_id": [cursor]})


def export_part(directory, index, partitions, partition):
    name = f"vectors-{partition+1:03}.jsonl.gz"
    output = directory / name
    partial = output.with_suffix(".part")
    rows = 0
    records = vector_slice(index, partitions, partition)
    try:
        with gzip.open(partial, "wt", encoding="utf-8", compresslevel=1) as stream:
            for hit in records:
                doc = hit["_source"]
                encoded = base64.b64encode(VECTOR.pack(*doc["embedding"])).decode(
                    "ascii"
                )
                checked_vector(encoded)
                stream.write(
                    json.dumps(
                        [hit["_id"], text_key(doc["comments"]), encoded],
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                rows += 1
    finally:
        records.close()
    partial.replace(output)
    return {"file": name, "rows": rows, "sha256": checksum(output)}


def export_vectors(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    source = context()
    expected = counts()
    if expected["vectors"] + expected["empty"] != expected["reviews"]:
        raise ValueError("Finish embedding generation before exporting")
    path = directory / "manifest.json"
    if path.exists():
        manifest = read_json(path)
        if any(
            manifest.get(k) != v
            for k, v in {**source, "counts": expected, "format": 2}.items()
        ):
            raise ValueError("Export directory belongs to another source generation")
    else:
        manifest = {
            "format": 2,
            **source,
            "counts": expected,
            "parts": [],
            "complete": False,
        }
    if manifest["complete"]:
        verify_files(directory, manifest)
        return {"complete": True, **expected}
    exported = sum(part["rows"] for part in manifest["parts"])
    verify_files(directory, manifest)
    if manifest.get("partitions", PARTITIONS) != PARTITIONS:
        raise ValueError("Export partition configuration changed")
    manifest["partitions"] = PARTITIONS
    with ProcessPoolExecutor(max_workers=4) as pool:
        for part in pool.map(
            partial(export_part, directory, INDEX, PARTITIONS),
            range(len(manifest["parts"]), PARTITIONS),
        ):
            manifest["parts"].append(part)
            exported += part["rows"]
            save_manifest(path, manifest)
            print(f"Exported {exported:,}/{expected['vectors']:,} vectors.", flush=True)
    if exported != expected["vectors"]:
        raise ValueError("Exported vector count differs from the source")
    if context() != source or counts() != expected:
        raise ValueError("The source changed during export")
    manifest["complete"] = True
    save_manifest(path, manifest)
    return {"complete": True, **expected}


def verify_files(directory, manifest):
    parts = manifest["parts"]
    if len({p["file"] for p in parts}) != len(parts):
        raise ValueError("Repeated embedding part")
    if manifest.get("complete") and (
        len(parts) != manifest["partitions"]
        or sum(p["rows"] for p in parts) != manifest["counts"]["vectors"]
    ):
        raise ValueError("Incomplete embedding part list")
    for part in manifest["parts"]:
        name = part["file"]
        if Path(name).name != name or checksum(directory / name) != part["sha256"]:
            raise ValueError("Missing or damaged embedding part: " + name)


def import_vectors(directory):
    require_ready()
    old = es("GET", INDEX + "/_settings")[INDEX]["settings"]["index"].get(
        "refresh_interval", "1s"
    )
    es("PUT", INDEX + "/_settings", {"index": {"refresh_interval": "-1"}})
    try:
        return _import_vectors(directory)
    finally:
        es("PUT", INDEX + "/_settings", {"index": {"refresh_interval": old}})
        es("POST", INDEX + "/_refresh")


def _import_vectors(directory):
    directory = Path(directory)
    manifest = read_json(directory / "manifest.json")
    if manifest.get("format") != 2 or not manifest.get("complete"):
        raise ValueError("Embedding export is incomplete or unsupported")
    if any(manifest.get(k) != v for k, v in context().items()):
        raise ValueError("Embeddings do not match the loaded sources/model")
    if counts()["reviews"] != manifest["counts"]["reviews"]:
        raise ValueError("Review counts differ from the export")
    verify_files(directory, manifest)
    processed = 0

    def write(batch):
        docs = es(
            "POST",
            INDEX + "/_mget",
            {
                "docs": [
                    {"_id": r[0], "_source": ["comments", "embedding_status"]}
                    for r in batch
                ]
            },
        )["docs"]
        lines = []
        for row, hit in zip(batch, docs):
            key, digest, encoded = row
            if (
                not hit.get("found")
                or text_key(hit["_source"].get("comments")) != digest
            ):
                raise ValueError("Review text changed: " + key)
            vector = checked_vector(encoded)
            if hit["_source"].get("embedding_status") == "ready":
                continue
            lines.extend(
                [
                    json.dumps({"update": {"_index": INDEX, "_id": key}}),
                    json.dumps(
                        {"doc": {"embedding": vector, "embedding_status": "ready"}}
                    ),
                ]
            )
        if lines:
            es("POST", "_bulk", lines=lines)

    for part in manifest["parts"]:
        rows, batch = 0, []
        with gzip.open(directory / part["file"], "rt", encoding="utf-8") as stream:
            for line in stream:
                batch.append(json.loads(line))
                rows += 1
                if len(batch) == BATCH_SIZE:
                    write(batch)
                    batch = []
            if batch:
                write(batch)
        if rows != part["rows"]:
            raise ValueError("Embedding part count differs")
        processed += rows
        print(f"Restored or retained {processed:,} vectors.", flush=True)
    # Empty canonical text needs no model inference.
    es("POST", INDEX + "/_refresh")
    lines = []
    for hit in scan(
        INDEX, {"bool": {"must_not": [{"exists": {"field": "embedding"}}]}}
    ):
        if clean_text(hit["_source"].get("comments")):
            raise ValueError("A non-empty review is missing its exported embedding")
        lines.extend(
            [
                json.dumps({"update": {"_index": INDEX, "_id": hit["_id"]}}),
                json.dumps({"doc": {"embedding_status": "empty"}}),
            ]
        )
        if len(lines) == BATCH_SIZE * 2:
            es("POST", "_bulk", lines=lines)
            lines = []
    if lines:
        es("POST", "_bulk", lines=lines)
    es("POST", INDEX + "/_refresh")
    if counts() != manifest["counts"]:
        raise ValueError("Restored embedding coverage differs from the export")
    return {"complete": True, **counts()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "import"))
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    with writer_lock(), report_run("embedding_" + args.action) as report:
        report.update(
            (export_vectors if args.action == "export" else import_vectors)(
                args.directory
            )
        )
