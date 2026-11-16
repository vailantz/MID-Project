# Virtual Data Integration System for Accommodation and Local Discovery in Lisbon — Project P1

This repository contains the work developed for the **Data Modelling and Integration (DMI)** course (Master's in Informatics Engineering, Universidade do Algarve), focused on the design, implementation, population, and quality assessment of autonomous heterogeneous local data sources in Lisbon (**Project P1**), preparing the foundation for virtual data integration in **Project P2**.

The core goal is to model and query complementary urban tourism subtopics across four distinct storage paradigms while preserving source autonomy, provenance, and declarative integrity:

- **Source B1 — Restaurants & Local Activity (PostgreSQL 16):** Relational catalogue of 5,261 Lisbon dining establishments and 12,167 cuisine/venue-type label associations (Tripadvisor snapshot), paired with a deterministic activity scenario (12 group representatives, 19 reservations, and 28 visits) enforced by natural composite candidate keys and declarative `CHECK` / `FOREIGN KEY` constraints.
- **Source B2 — Cultural Heritage (BaseX 12.4 Native XML):** Hierarchical XML catalogue of 130 municipal cultural records (67 museums and 63 monuments from Câmara Municipal de Lisboa), validated against `catalogue.xsd` (`xs:key` / `xs:keyref`, `xsi:nil`) and queried via XPath and XQuery.
- **Source A1 — Guest Reviews Corpus (Elasticsearch):** Inverted lexical (BM25) and optional vector (`int8_hnsw`, 1,024-dim Qwen3-Embedding-4B) index over 1,950,076 logical guest reviews (1,964,992 observations) and 1,762,796 person profiles from Inside Airbnb.
- **Source A2 — Accommodation & Price Quotes (MongoDB):** Document database storing 25,020 accommodation listings, 9,484 host/owner profiles with identity-document validation, and 23,661 price-quote families (24,861 monetary observations), with `2dsphere` geospatial indexing and JSON Schema validators.

---

## Report

The formal academic report for **Project P1** is available in [`report/`](report/):

- **[English Report (PDF)](report/Report_P1_Tiago_Goncalo_English.pdf)** — Compiled Project P1 report
- Complete LaTeX source files (`main.tex`, `sections/`), ER diagrams (`der_tiago.png`, `der_goncalo_owner_en.pdf`), and bibliography are maintained in [`report/`](report/).

---

## Repository Structure

| Directory / File | Description |
| :--- | :--- |
| [`report/`](report/) | Compiled Project P1 report ([`Report_P1_Tiago_Goncalo_English.pdf`](report/Report_P1_Tiago_Goncalo_English.pdf)), ER diagrams ([`der_tiago.png`](report/der_tiago.png), [`der_goncalo_owner_en.pdf`](report/der_goncalo_owner_en.pdf)), and complete LaTeX source files ([`main.tex`](report/main.tex), [`sections/`](report/sections/)). |
| [`Dev/`](Dev/) | Implementation of **Sources B1 (PostgreSQL 16)** and **B2 (BaseX 12.4 XML)**: schemas, profiling/loading/validation scripts, SQL & XQuery queries, synthetic activity fixtures, and validation reports. |
| [`Dev/data/`](Dev/data/) | Municipal cultural XML working copy (`cultural_catalogue.xml`), deterministic synthetic activity fixtures (`synthetic_activity.json`), and SHA-256 provenance manifest (`provenance.json`). |
| [`Dev/postgresql/`](Dev/postgresql/) | Relational 3NF schema (`01_schema.sql`), deterministic generated SQL (`generated/full_catalogue.sql`, `generated/synthetic_activity.sql`), quality checks (`04_quality.sql`), GAV views (`05_views_and_unfolding.sql`), and P1 activity queries (`06_p1_activity_queries.sql`). |
| [`Dev/xml_basex/`](Dev/xml_basex/) | XML Schema (`catalogue.xsd`) and XQuery scripts (`01_museums.xq` to `06_p1_quality.xq`) over the municipal cultural catalogue (`Dev/data/cultural_catalogue.xml`). |
| [`Dev/scripts/`](Dev/scripts/) | Automated Python and PowerShell preparation and verification scripts (`profile_source.py`, `prepare_full_catalogue.py`, `prepare_synthetic_activity.py`, `check_full_catalogue.py`, `check_basex_p1.py`, `basex_p1.ps1`). |
| [`Dev/results/`](Dev/results/) | Consolidated execution logs, SHA-256 provenance manifests, XML/XQuery outputs (`basex_p1/`), and JSON validation reports. |
| [`Fontes/`](Fontes/) | Preserved original datasets and provenance metadata (`Tripadvisor_Kaggle/`, `Camara_Municipal/`, `InsideAirbnb/`). |
| [`Docs/`](Docs/) | Official course project brief ([`DMI_Projects_2026_2027.pdf`](Docs/DMI_Projects_2026_2027.pdf)) and project proposal ([`project_proposal.pdf`](Docs/project_proposal.pdf)). |

---

## Requirements

### Sources B1 & B2 (`Dev/`)
- **OS:** Windows x64
- **Python:** $\ge 3.11$ (with `lxml` for XSD validation)
- **PostgreSQL:** $\ge 16$ (`initdb`, `pg_ctl`, `psql`, `createdb` binaries)
- **Java & BaseX:** Java $\ge 17$ (uses the self-contained `Dev/tools/BaseX124.jar` included in the repository)

### Sources A1 & A2 (`z_Code/`)
- **OS:** Windows x64
- **Python:** $\ge 3.10$
- **Services:** MongoDB and Elasticsearch (pinned versions managed by `setup.ps1`)

---

## Reproducibility & Quickstart Guide

### Step 1: Clone the Repository
```powershell
git clone https://github.com/vailantz/MID-Project.git
cd MID-Project
```

### Step 2: Run & Validate Sources B1 (PostgreSQL) and B2 (BaseX XML)
From [`Dev/`](Dev/):

```powershell
cd Dev

# 1. Profile the original Lisbon CSV extract (5,261 establishments) and generate the quality report
python -X utf8 scripts/profile_source.py

# 2. Generate deterministic SQL scripts for the real catalogue and synthetic activity scenario
python -X utf8 scripts/prepare_full_catalogue.py
python -X utf8 scripts/prepare_synthetic_activity.py

# 3. Launch an isolated PostgreSQL instance (port 55441, db tiago_p1), load data, and run all 16 + 38 checks
python -X utf8 scripts/check_full_catalogue.py
python -X utf8 scripts/check_full_catalogue.py --with-activity

# 4. Validate XML against XSD, build the BaseX database (tiago_culture_p1, 130 places), and run all 36 checks
python -X utf8 scripts/check_basex_p1.py

# 5. Execute individual XQuery scripts against the BaseX database
powershell -ExecutionPolicy Bypass -File scripts/basex_p1.ps1 -i tiago_culture_p1 -Q xml_basex/01_museums.xq
```

> **Interactive Inspection Note:** Append `--keep-open` to `python -X utf8 scripts/check_full_catalogue.py --with-activity --keep-open` to keep the isolated PostgreSQL instance running on `127.0.0.1:55441` (`database=tiago_p1`, `user=dmi_p1`, `schema=tiago_lab`) for live inspection during demonstrations.

### Step 3: Run & Validate Sources A1 (Elasticsearch) and A2 (MongoDB)
From the `z_Code/` package directory:

```powershell
# 1. Install pinned services, prepare inputs, load A1/A2, and execute verification tests
powershell -ExecutionPolicy Bypass -File setup.ps1

# 2. Run local queries and verification checks on MongoDB (A2) and Elasticsearch (A1)
.\.venv\Scripts\python.exe scripts/ingest.py --properties
.\.venv\Scripts\python.exe scripts/ingest.py --quotes 6499 --quote-policy latest-valid
.\.venv\Scripts\python.exe scripts/ingest.py --search "quiet apartment"
.\.venv\Scripts\python.exe scripts/test_databases.py
```

---

## Individual Contributions

- **Tiago Vailant (`a79922`):** Dining, cultural heritage, and local activity subtopic (**Source B1** in PostgreSQL and **Source B2** in BaseX XML, `Dev/` directory) and specification of integrated queries **Q03, Q04, Q07, Q08, Q10, and Q12**.
- **Gonçalo Serafim (`a79189`):** Accommodation, guest reviews, owner documentation, and price quotes subtopic (**Source A1** in Elasticsearch and **Source A2** in MongoDB, `z_Code/` package) and specification of integrated queries **Q01, Q02, Q05, Q06, Q09, and Q11**.
- **Joint Work:** Shared domain glossary, heterogeneity and conflict resolution matrix for Phase P2, and consolidation of the final report.

---

## Credits

This project made limited use of generative AI tools (conversational LLM assistants) to support LaTeX formatting, text revision, and auxiliary profiling and diagram-generation scripts. All schemas, integrity constraints, reconciliation rules, code, and queries were locally executed and verified by the authors, who assume full responsibility for the submitted work.

---

## Authors

**Tiago Vailant**
- **Student ID:** a79922
- **Institutional Email:** a79922@ualg.pt
- **Institution:** Universidade do Algarve

**Gonçalo Serafim**
- **Student ID:** a79189
- **Institutional Email:** a79189@ualg.pt
- **Institution:** Universidade do Algarve
