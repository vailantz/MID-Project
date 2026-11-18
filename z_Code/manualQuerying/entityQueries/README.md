# Editable entity queries

One self-contained query for each MongoDB collection and ES index. Run from
`z_Code` in PowerShell, with MongoDB and ES already running. Qwen is not required.

| File | Default query |
|---|---|
| `es_reviews.json` | Recent reviews containing both quiet and apartment, score 4–5; highlights and aggregate statistics |
| `es_people.json` | People named Ana with a known phone; roles, owner identification, history and aggregate statistics |
| `mongo_accommodation.py` | Lisboa, capacity 2–8, Wifi and Kitchen, rating at least 4.8; location, host/owner links and history |
| `mongo_people.py` | Host profiles with a known Portugal/UK phone; identity, contact, roles and history |
| `mongo_owners.py` | Active owners with documents expired on `AS_OF`; identity, activity and recalculated document status |
| `mongo_price_quotes.py` | Quote families containing a EUR observation of 50–150, with its billing basis and history |

## MongoDB

```powershell
.\.venv\Scripts\python.exe manualQuerying/entityQueries/mongo_accommodation.py
.\.venv\Scripts\python.exe manualQuerying/entityQueries/mongo_people.py
.\.venv\Scripts\python.exe manualQuerying/entityQueries/mongo_owners.py
.\.venv\Scripts\python.exe manualQuerying/entityQueries/mongo_price_quotes.py
```

Edit the constants at the top: `FILTER` selects records, `PROJECTION` selects
fields, `SORT` orders them, and `SKIP`/`LIMIT` select a page. Sort ties use the
entity ID. Output includes the total match count and the returned records.

- Set `FILTER = {}` for all records, or add/remove individual conditions.
- Ordinary adjacent conditions mean AND; `$in` permits alternatives and `$all`
  requires every listed array member. Projections use `1` to include fields.
- Person/Accommodation histories show the first three observations; quotes show
  the first five. Change `$slice`, or use `"observations": 1` for full history.
- Owner aggregation's `$set` changes the returned values only. Changing `AS_OF`
  recalculates document expiry, while activity keeps its stored assessment date.
- The quote filter's `$elemMatch` requires currency, amount and basis to match
  within the **same observation**. Returned history can also contain other
  observations. No `latest-valid` or `agreement-only` decision is applied, and
  unspecified prices must not be interpreted as nightly prices.

## Elasticsearch

Reviews:

```powershell
Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:9200/dmi-79189-v2-reviews/_search" `
    -ContentType "application/json" `
    -InFile .\manualQuerying\entityQueries\es_reviews.json |
    ConvertTo-Json -Depth 30
```

People:

```powershell
Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:9200/dmi-79189-v2-people/_search" `
    -ContentType "application/json" `
    -InFile .\manualQuerying\entityQueries\es_people.json |
    ConvertTo-Json -Depth 30
```

Edit `query.bool.must` for text, `filter` for required restrictions, and `must_not`
for exclusions. `terms` on roles accepts either listed role. `match` with
`operator: "and"` requires all words; replace it with `match_phrase` for a phrase.
Remove text clauses to browse by filters alone.

`_source` controls returned fields, `sort` controls ordering, and `from`/`size`
select a page. `track_total_hits` requests an exact match count. `aggs` summarises
**all matching documents**, not just the page; role buckets can overlap.
ES history/resolution is returned but cannot be filtered because it is not indexed.

See [the syntax guide](../manualQueryingGuide.md) for operators and system fields.
