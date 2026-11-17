# Sources A1 and A2 — Gonçalo Serafim

Windows x64; Python 3.10 or newer. Run commands from this folder.

## First setup

From the repository root, download the Git LFS files first:

```powershell
git lfs install
git lfs pull
cd z_Code
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Setup installs portable MongoDB/Elasticsearch, prepares the supplied originals,
loads both sources, imports the completed embeddings and runs the tests.
If MongoDB 8.x and Elasticsearch 8.19.x are already running on localhost ports
27017 and 9200, use `setup.ps1 -UseExisting` instead. Only database `dmi_79189_v2`
and indices `dmi-79189-v2-reviews` and `dmi-79189-v2-people` are replaced.
Allow 100 GB free space for installation, generated data and vector indexing.

## Later sessions and queries

Start your existing services, or start the portable services installed by setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\database\start.ps1
.\.venv\Scripts\python.exe scripts/ingest.py --properties
.\.venv\Scripts\python.exe scripts/ingest.py --quotes 6499
.\.venv\Scripts\python.exe scripts/ingest.py --search "quiet apartment"
.\.venv\Scripts\python.exe scripts/ingest.py --renewals --as-of 2026-11-13
.\.venv\Scripts\python.exe scripts/test_databases.py
```

Do not rerun setup to query existing sources: setup rebuilds them. The portable
services can be stopped with `powershell -ExecutionPolicy Bypass -File .\database\stop.ps1`.

## Semantic search

For the first semantic query, prepare a separate GPU environment. This uses
the [official CUDA 12.8 PyTorch package](https://pytorch.org/get-started/previous-versions/)
and requires an NVIDIA GPU (the encoder was tested with 32 GB VRAM):

```powershell
.\.venv\Scripts\python.exe -m venv .venv-embeddings
.\.venv-embeddings\Scripts\python.exe -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cu128
.\.venv-embeddings\Scripts\python.exe -m pip install -r requirements-embeddings.txt
.\.venv-embeddings\Scripts\python.exe scripts/nlp.py --query "a peaceful place to sleep"
```

Qwen's pinned model is downloaded if it is not cached. The query is embedded
locally and searches the imported review vectors; review embeddings are not
regenerated. BM25 and MongoDB queries do not need the model or a GPU.
The bundle contains 1,935,112 vectors; the other 14,964 reviews have no usable
text and remain unembedded.

## Files

- `data/original/`: unchanged supplied review CSV and property JSON.
- `data/embeddings/`: completed vectors in compressed parts, with counts,
  model configuration and SHA-256 checksums in `manifest.json`.
- `scripts/data.py`: reproducible contacts, scores, owner documents and controlled
  quality cases; produces `data/current/` and preparation evidence.
- `scripts/ingest.py`, `rules.py`, `owners.py`, `quotes.py`: loading, validation,
  reconciliation and local queries. Price policies are applied at retrieval.
- `scripts/embeddings.py`: resumable vector export/import, with source and text checks.
- `scripts/nlp.py`, `encoder.py`: model encoding and kNN queries.
- `database/`: mappings, validators and portable service commands.
- `scripts/test_*.py`: unit and live database checks.
- `docs/entity_examples.pdf`: stored entity examples.

Generated files, environments, database storage and execution reports are ignored
by Git. Originals and vector parts use Git LFS. The prepared sources contain
1,950,076 logical reviews, 25,020 properties and 9,484 owners. Owner activity uses
13 November 2026; document queries accept `--as-of`, defaulting to today.

Original content: [Inside Airbnb, Lisbon](https://insideairbnb.com/get-the-data/),
19 September 2026 snapshot, supplied extracts acquired 14 October 2026, CC BY 4.0.
Contacts, individual review scores, identity documents and observation times are
synthetic exercise data.
