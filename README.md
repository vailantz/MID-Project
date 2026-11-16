# Virtual Data Integration System for Accommodation and Local Discovery in Lisbon — Project P1

This repository contains the work developed for the **Data Modelling and Integration (DMI)** course (Master's in Informatics Engineering, UALG), focused on the design, implementation, population, and quality assessment of autonomous heterogeneous local data sources in Lisbon, preparing the foundation for virtual data integration.

The core goal is to model and query complementary urban tourism subtopics across four distinct storage paradigms while preserving source autonomy, provenance, and declarative integrity:

- **Source B1 — Restaurants & Local Activity (PostgreSQL 16):** Relational catalogue of 5,261 Lisbon dining establishments and 12,167 cuisine/venue-type label associations (Tripadvisor snapshot), paired with a deterministic activity scenario (12 group representatives, 19 reservations, and 28 visits) enforced by natural composite candidate keys and declarative `CHECK` / `FOREIGN KEY` constraints.
- **Source B2 — Cultural Heritage (BaseX 12.4 Native XML):** Hierarchical XML catalogue of 130 municipal cultural records (67 museums and 63 monuments from Câmara Municipal de Lisboa), validated against `catalogue.xsd` (`xs:key` / `xs:keyref`, `xsi:nil`) and queried via XPath and XQuery.
- **Source A1 — Guest Reviews Corpus (Elasticsearch):** Inverted lexical (BM25) and optional vector (`int8_hnsw`, 1,024-dim Qwen3-Embedding-4B) index over 1,950,076 logical guest reviews (1,964,992 observations) and 1,762,796 person profiles from Inside Airbnb.
- **Source A2 — Accommodation & Price Quotes (MongoDB):** Document database storing 25,020 accommodation listings, 9,484 host/owner profiles with identity-document validation, and 23,661 price-quote families (24,861 monetary observations), with `2dsphere` geospatial indexing and JSON Schema validators.

---

## Report

The formal academic report for **Project P1** is available in [`report/`](report/):

- **[English Report (PDF)](report/Report_P1.pdf)** — Compiled Project P1 report
- Complete LaTeX source files (`main.tex`, `sections/`), ER diagrams (`der_tiago.png`, `der_goncalo_owner_en.pdf`), and bibliography are maintained in [`report/`](report/).

---

## Repository Structure

| Directory / File | Description |
| :--- | :--- |
| [`report/`](report/) | Compiled Project P1 report ([`Report_P1.pdf`](report/Report_P1.pdf)), ER diagrams ([`der_tiago.png`](report/der_tiago.png), [`der_goncalo_owner_en.pdf`](report/der_goncalo_owner_en.pdf)), and complete LaTeX source files ([`main.tex`](report/main.tex), [`sections/`](report/sections/)). |
| [`Dev/`](Dev/) | Implementation of **Sources B1 (PostgreSQL 16)** and **B2 (BaseX 12.4 XML)**: schemas, profiling/loading/validation scripts, SQL & XQuery queries, synthetic activity fixtures, and validation reports. |
| [`Dev/run.cmd`](Dev/run.cmd) | Make-style shortcut runner (`run all`, `run pg`, `run sql`, `run psql`, `run xml`, `run xquery`, `run clean`) with automatic UTF-8 configuration. |
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
From [`Dev/`](Dev/), use the [`run.cmd`](Dev/run.cmd) shortcut runner (works in both CMD and PowerShell with UTF-8 preconfigured):

```cmd
cd Dev

run           # Display all available shortcut commands
run all       # Run full pipeline (CSV profile + 38 PostgreSQL checks + 36 BaseX XML checks)
run profile   # Profile the original Lisbon CSV extract (5,261 establishments)
run pg        # Launch isolated PostgreSQL B1 (port 55441), run 38 checks, and keep open
run sql       # Execute P1 SQL queries (06_p1_activity_queries.sql) against open instance
run psql      # Open interactive PostgreSQL shell (tiago_p1=#) in UTF-8
run xml       # Validate XML against XSD and run all 36 BaseX B2 checks
run xquery    # Execute BaseX XQuery scripts (02_counts.xq, 01_museums.xq, or custom .xq)
run clean     # Clean temporary runtime folders (.runtime and __pycache__)
```

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
