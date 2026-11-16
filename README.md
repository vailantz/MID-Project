# MID Project — Phase 1 (P1): Data Modeling & Heterogeneous Sources

Repository for **Phase 1 (P1)** of the **Data Modeling and Integration (MID)** project (M.Sc. in Computer Engineering, University of Algarve, 2026/2027).

The project models and prepares four heterogeneous data sources covering tourism, accommodation, dining, and cultural heritage in **Lisbon**, establishing the local schemas, integrity constraints, data quality profiles, and the 12 local and cross-source queries required for virtual integration in Phase 2.

---

## Architecture & Data Sources

| Source | Subtopic | Engine | Paradigm | Records | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A1** | Accommodation Reviews & Text | **Elasticsearch 8.15** | Document / Inverted Index | 1,950,076 reviews | Gonçalo Serafim (`79189`) |
| **A2** | Accommodation Listings & Quotes | **MongoDB 7.0** | Document JSON (`$jsonSchema`) | 25,020 listings + 150,120 quotes | Gonçalo Serafim (`79189`) |
| **B1** | Dining Establishments & Activity | **PostgreSQL 16** | Relational SQL | 5,261 establishments + synthetic activity | Tiago Vailant (`79922`) |
| **B2** | Cultural Heritage (Museums & Monuments) | **BaseX 12.4** | Native XML (`XSD 1.0` / `XQuery 3.1`) | 130 places (67 museums, 63 monuments) | Tiago Vailant (`79922`) |

---

## Repository Structure

```text
.
├── report/
│   ├── Report_P1_Tiago_Goncalo_English.pdf   # Final Phase 1 Report (PDF)
│   ├── main.tex                              # LaTeX master document
│   ├── der_tiago.png                         # ER diagram for Subtopic B (B1 + B2)
│   ├── der_goncalo_owner_en.pdf              # ER diagram for Subtopic A (A1 + A2)
│   └── sections/                             # Modular LaTeX sections (00_capa .. 09_execucao)
├── Dev/                                      # Subtopic B implementation (PostgreSQL B1 + BaseX B2)
│   ├── data/                                 # XML cultural catalogue, provenance & synthetic activity fixtures
│   ├── postgresql/                           # Relational DDL (01_schema.sql), quality checks, GAV views & SQL queries
│   ├── xml_basex/                            # XML Schema (catalogue.xsd) & XQuery scripts (.xq)
│   ├── scripts/                              # Deterministic preparation & validation pipelines
│   ├── tools/                                # BaseX 12.4 standalone engine
│   └── results/                              # Automated validation logs & query outputs
├── z_Code/                                   # Subtopic A implementation (Elasticsearch A1 + MongoDB A2)
│   ├── docker-compose.yml                    # Container orchestration for MongoDB & Elasticsearch
│   └── p1_a1_a2/                             # Loader, index mappings, JSON Schema & validation scripts
├── Fontes/                                   # Preserved raw datasets & provenance manifests
│   ├── Camara_Municipal/                     # Lisbon Municipal Open Data (Museums & National Monuments)
│   ├── InsideAirbnb/                         # Inside Airbnb Lisbon listings & reviews
│   └── Tripadvisor_Kaggle/                   # TripAdvisor European Restaurants (Lisbon extract)
└── Docs/                                     # Course assignment specification & initial proposal
```

---

## Reproducing the Local Sources & Validation

### Subtopic B — PostgreSQL (`B1`) & BaseX XML (`B2`)
Requires **Python 3.11+**, **PostgreSQL 16**, and **Java 17+**. From `Dev/`:

```bash
# Validate and load the full Lisbon restaurant catalogue (5,261 establishments) + synthetic activity (38 checks)
python -X utf8 scripts/check_full_catalogue.py --with-activity

# Validate the cultural XML catalogue against XSD 1.0 and execute all BaseX XQuery checks (36 checks)
python -X utf8 scripts/check_basex_p1.py
```

### Subtopic A — Elasticsearch (`A1`) & MongoDB (`A2`)
Requires **Docker** and **Python 3.11+**. From `z_Code/`:

```bash
docker compose up -d
python p1_a1_a2/run_p1_a1_a2.py
```

---

## Authors & Contributions

- **Gonçalo Serafim (`79189`):** Accommodation, reviews, and price quotes subtopic (sources **A1** in Elasticsearch and **A2** in MongoDB, `z_Code/` package) and specification of integrated queries **Q01, Q02, Q05, Q06, Q09, and Q11**.
- **Tiago Vailant (`79922`):** Dining, cultural heritage, and local activity subtopic (sources **B1** in PostgreSQL and **B2** in BaseX XML, `Dev/` directory) and specification of integrated queries **Q03, Q04, Q07, Q08, Q10, and Q12**.
- **Joint Work:** Common semantic glossary, integration conflict matrix for Phase 2 (P2), and report consolidation.
- **Generative AI Disclosure:** Generative AI tools (LLM assistants) were used to assist with LaTeX formatting, text revision, and auxiliary profiling and diagram-generation scripts. All schemas, integrity constraints, reconciliation rules, code, and queries were locally validated and executed by the authors, who take full responsibility for the final content.
