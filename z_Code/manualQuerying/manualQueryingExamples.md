# Query commands

Run these commands from `z_Code` in PowerShell, with the required services running.

## Queries for every entity

See [entityQueries/README.md](entityQueries/README.md) for six editable templates
and their run commands: two ES indices and four MongoDB collections.

## MongoDB accommodation query

Returns five listings in Lisboa with capacity of at least two, Wifi, and a rating
of at least 4.8, ordered by descending rating. This uses PyMongo directly.

```powershell
.\.venv\Scripts\python.exe manualQuerying/mongodb_accommodations.py
```

## Keyword search using JSON

Edit `query.match.comments` in `pink_house_bm25.json` to change the search text.

```powershell
Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:9200/dmi-79189-v2-reviews/_search" `
    -ContentType "application/json" `
    -InFile .\manualQuerying\pink_house_bm25.json |
    ConvertTo-Json -Depth 30
```

## Semantic search using JSON

`pink_house_knn.json` contains both requests. Edit `encode.text` to change the
search text, or `search.knn` to change `k` and `num_candidates`. Qwen's response
fills the empty `query_vector` in memory.

```powershell
$query = Get-Content .\manualQuerying\pink_house_knn.json -Raw -Encoding UTF8 | ConvertFrom-Json

$query.search.knn.query_vector = (Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8791/encode" `
    -ContentType "application/json" `
    -Body ($query.encode | ConvertTo-Json)
).vector

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:9200/dmi-79189-v2-reviews/_search" `
    -ContentType "application/json" `
    -Body ($query.search | ConvertTo-Json -Depth 10) |
    ConvertTo-Json -Depth 30
```
