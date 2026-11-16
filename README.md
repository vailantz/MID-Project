# Sistema Virtual de Integração de Dados para Alojamento e Descoberta Local em Lisboa — Projeto P1

**Unidade Curricular:** Modelação e Integração de Dados (2026/2027) — Mestrado em Engenharia Informática, Universidade do Algarve  
**Docente:** Prof.ª Doutora Paula Cristina Negrão Ventura Martins  
**Grupo:**
- **Gonçalo Serafim (N.º 79189)** — Subtópico A: *Alojamento, Avaliações de Hóspedes e Cotações de Preço* (Fontes **A1** em Elasticsearch e **A2** em MongoDB)
- **Tiago Alexandre Vailant (N.º 79922)** — Subtópico B: *Oferta Cultural, Restauração e Atividade Local* (Fontes **B1** em PostgreSQL e **B2** em BaseX XML)

---

## 1. Estrutura do Projeto

| Diretório / Ficheiro | Descrição |
| :--- | :--- |
| [`report/`](report/) | Relatório da Fase P1: PDFs compilados ([`Report_P1_Tiago_Goncalo_clean.pdf`](report/Report_P1_Tiago_Goncalo_clean.pdf) e [`Report_P1_Tiago_Goncalo_orange.pdf`](report/Report_P1_Tiago_Goncalo_orange.pdf)) e respetivas pastas de código LaTeX ([`report/latex_clean/`](report/latex_clean/) e [`report/latex_orange/`](report/latex_orange/)). |
| [`Dev/`](Dev/README.md) | Implementação das fontes **B1 (PostgreSQL 16)** e **B2 (BaseX 12.4 XML)** de Tiago Vailant: esquemas, scripts de perfilagem/carga/verificação, consultas SQL e XQuery, dados sintéticos e relatórios de validação. |
| [`Dev/models/`](Dev/models/) | Diagramas concetuais ([`der_tiago.png`](Dev/models/der_tiago.png), [`der_goncalo.png`](Dev/models/der_goncalo.png)), especificações dos modelos lógicos/físicos (`04_postgresql_p1.md`, `05_cenario_sintetico_p1.md`, `06_xml_basex_p1.md`) e catálogo das consultas (`03_consultas_p1.md`). |
| [`Dev/postgresql/`](Dev/postgresql/README_P1.md) | Esquema relacional 3NF (`01_schema.sql`), scripts SQL gerados (`generated/full_catalogue.sql`, `generated/synthetic_activity.sql`) e consultas locais (`03_queries.sql`, `04_quality.sql`, `05_views_and_unfolding.sql`). |
| [`Dev/xml_basex/`](Dev/xml_basex/README_P1.md) | Esquema XML (`catalogue.xsd`), catálogo municipal (`data/cultural_catalogue.xml`), manifesto de proveniência (`data/provenance.json`) e 6 consultas XQuery (`01_museums.xq` a `06_p1_quality.xq`). |
| [`Dev/scripts/`](Dev/scripts/) | Scripts Python/PowerShell de perfilagem, preparação e verificação automatizada (`profile_source.py`, `prepare_full_catalogue.py`, `prepare_synthetic_activity.py`, `check_full_catalogue.py`, `check_basex_p1.py`, `basex_p1.ps1`). |
| [`Fontes/`](Fontes/) | Conjuntos de dados originais preservados sem alterações (`Tripadvisor_Kaggle/`, `Camara_Municipal/`, `InsideAirbnb/`) e notas de proveniência. |
| [`Docs/`](Docs/) | Enunciado oficial (`DMI_Projects_2026_2027.pdf`) e proposta aceite (`project_proposal.pdf`). |
| `z_Code/` | Pacote autónomo das fontes **A1 (Elasticsearch)** e **A2 (MongoDB)** de Gonçalo Serafim (`setup.ps1`, `database/`, `scripts/`, `models/`). |

---

## 2. Instruções de Instalação, Povoamento e Verificação

### 2.1 Fontes B1 (PostgreSQL) e B2 (BaseX XML) — Tiago Vailant (`Dev/`)

**Pré-requisitos:** Windows x64, Python 3.11+ (com pacote `lxml`), PostgreSQL 16+ (`initdb`, `pg_ctl`, `psql`) e Java 17+ (usa `Dev/tools/BaseX124.jar` incluído).

A partir da pasta [`Dev/`](Dev/):

```powershell
# 1. Perfilar o CSV original de Lisboa (5 261 estabelecimentos) e gerar o relatório de qualidade
python -X utf8 scripts/profile_source.py

# 2. Gerar os scripts SQL determinísticos do catálogo real e do cenário sintético de atividade
python -X utf8 scripts/prepare_full_catalogue.py
python -X utf8 scripts/prepare_synthetic_activity.py

# 3. Iniciar instância PostgreSQL isolada (porta 55441, base tiago_p1), carregar dados e validar (16 + 37 controlos)
python -X utf8 scripts/check_full_catalogue.py --with-activity

# 4. Validar XSD, criar a base BaseX tiago_culture_p1 (130 lugares culturais) e validar (36 controlos)
python -X utf8 scripts/check_basex_p1.py

# 5. Executar individualmente qualquer consulta XQuery sobre a base BaseX
powershell -ExecutionPolicy Bypass -File scripts/basex_p1.ps1 -i tiago_culture_p1 -Q xml_basex/01_museums.xq
```

> Para manter a instância PostgreSQL da P1 aberta para inspeção em `psql`, `pgAdmin` ou Prisma Studio (`npm run studio:p1`), acrescentar `--keep-open` ao comando `check_full_catalogue.py --with-activity`.

---

### 2.2 Fontes A1 (Elasticsearch) e A2 (MongoDB) — Gonçalo Serafim (`z_Code/`)

**Pré-requisitos:** Windows x64, Python 3.10+ e acesso à Internet na primeira instalação.

A partir da pasta do pacote `z_Code/`:

```powershell
# 1. Instalar versões fixadas dos serviços, preparar entradas, carregar A1/A2 e executar testes
powershell -ExecutionPolicy Bypass -File setup.ps1

# 2. Consultas e controlos locais em MongoDB (A2) e Elasticsearch (A1)
.\.venv\Scripts\python.exe scripts/ingest.py --properties
.\.venv\Scripts\python.exe scripts/ingest.py --quotes 6499 --quote-policy latest-valid
.\.venv\Scripts\python.exe scripts/ingest.py --search "quiet apartment"
.\.venv\Scripts\python.exe scripts/test_databases.py
```

---

## 3. Declaração de Contribuições e Uso de IA Generativa

- **Contribuições Individuais:**
  - **Gonçalo Serafim (79189):** Subtópico de alojamento, avaliações e cotações de preço (fontes A1 em Elasticsearch e A2 em MongoDB, pacote `z_Code`) e especificação das consultas integradas **Q01, Q02, Q05, Q06, Q09 e Q11**.
  - **Tiago Vailant (79922):** Subtópico de restauração, património cultural e atividade local (fontes B1 em PostgreSQL e B2 em BaseX XML, pasta `Dev`) e especificação das consultas integradas **Q03, Q04, Q07, Q08, Q10 e Q12**.
  - **Trabalho Conjunto:** Glossário semântico comum, matriz de conflitos de integração para a fase P2 e consolidação do relatório.
- **Uso de IA Generativa:** Ferramentas de IA generativa (assistentes LLM) foram utilizadas como apoio na formatação LaTeX, revisão de texto e scripts auxiliares de perfilagem e geração de diagramas. Todos os esquemas, restrições de integridade, regras de reconciliação, código e consultas foram validados e executados localmente pelos autores, que assumem total responsabilidade pelo trabalho entregue.
