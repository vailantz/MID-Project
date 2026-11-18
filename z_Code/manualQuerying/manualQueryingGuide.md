# Manual querying: quick guide

Edit an example, save it, then rerun its command in
[manualQueryingExamples.md](manualQueryingExamples.md). Run commands from `z_Code`;
MongoDB/ES must be running, plus Qwen for semantic search.

## Our system

MongoDB: `mongodb://127.0.0.1:27017`, database `dmi_79189_v2`.
ES: `http://127.0.0.1:9200`. Qwen: `http://127.0.0.1:8791`.

| Target | Useful fields |
|---|---|
| Mongo `accommodation` | `listing_id`, `name`, `capacity`, `amenities`, `ratings.rating`, `location.municipality`, `location.neighbourhood`, `host_person_id`, `owner_id` |
| Mongo `people` (hosts) | `person_id`, `name`, `phone_country`, `phone_number`, `roles` |
| Mongo `owners` | `owner_id`, `person_id`, `active`, `needs_renewal`, `identity_document.expires_on`, `reference_dates` |
| Mongo `price_quotes` | `quote_id`, `listing_id`, `origin`, `observations.values.amount`, `observations.values.currency` |
| ES `dmi-79189-v2-reviews` | `review_id`, `listing_id`, `person_id`, `comments`, `date`, `review_score` |
| ES `dmi-79189-v2-people` | `person_id`, `name`, `phone`, `roles`, `owner_id`, `identity_document` for owners |

IDs are **strings**. Use exact values such as `"Lisboa"` and `"Wifi"`; ratings use
0–5. Dotted paths address nested fields. `date` is a review's publication date;
`observed_at` dates its recorded observation. `observations` holds history;
normal searches use the selected top-level values. ES histories and `resolution`
are stored but not indexed for filtering.

## MongoDB: edit `mongodb_accommodations.py`

`find(FILTER, PROJECTION).sort(FIELD, DIRECTION).limit(N)` controls selection,
returned fields, order and result count. Replace the **first dictionary**, for example:

```python
{
    "location.municipality": "Sintra",
    "capacity": {"$gte": 4},
    "ratings.rating": {"$gte": 4.5},
    "amenities": {"$all": ["Wifi", "Kitchen"]}
}
```

| Filter syntax | Meaning |
|---|---|
| `"capacity": 4` | Exactly four |
| `"capacity": {"$gte": 2, "$lte": 6}` | Between two and six, inclusive |
| `$gt`, `$lt`, `$ne` | Greater than, less than, not equal |
| `"amenities": "Wifi"` | Array contains Wifi |
| `"location.municipality": {"$in": ["Lisboa", "Sintra"]}` | Either municipality |
| `"$or": [{"capacity": 2}, {"capacity": 4}]` | Either condition; ordinary adjacent conditions use AND |

In the **second dictionary**, `1` includes a field; `0` excludes it. Keep `_id: 0`
to hide the internal ID. Do not mix other exclusions with inclusions. Omit the
projection to return full documents. Sort direction: `1` ascending, `-1` descending.
Change `.limit(5)` for more results. Python uses `None`, `True`, `False`; JSON uses
`null`, `true`, `false`. A Mongo filter value of `None` matches null **or missing**.
See MongoDB's [filters](https://www.mongodb.com/docs/manual/tutorial/query-documents/)
and [projections](https://www.mongodb.com/docs/manual/tutorial/project-fields-from-query-results/).

## ES keywords: edit `pink_house_bm25.json`

| Replace the `query` entry with | Meaning |
|---|---|
| `"query": {"match": {"comments": "pink house"}}` | Pink OR house, ranked by relevance |
| `"query": {"match": {"comments": {"query": "pink house", "operator": "and"}}}` | Both words, anywhere |
| `"query": {"match_phrase": {"comments": "pink house"}}` | Adjacent words in order, after text analysis |

Combine text search and restrictions by replacing that entry with:

```json
"query": {
  "bool": {
    "must": [{"match_phrase": {"comments": "pink house"}}],
    "filter": [
      {"term": {"listing_id": "6499"}},
      {"range": {"date": {"gte": "2025-01-01"}}}
    ]
  }
}
```

`must` affects relevance; `filter` requires conditions without adding scores.
Use `term` for exact IDs, and `range` with `gt/gte/lt/lte` for dates or numbers.
ES operators have **no `$` prefix**. See [match](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/query-dsl-match-query.html),
[phrase](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/query-dsl-match-query-phrase.html)
and [Boolean queries](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/query-dsl-bool-query.html).

Other top-level settings: `size` limits results; `_source` selects returned content;
excluding `embedding` hides its 1,024 numbers without disabling vector search.
`highlight` returns matching excerpts. Add `"sort": [{"date": "desc"}]` for newest
reviews first instead of the default relevance order. Results are in `hits.hits`;
`_source` contains the document. `_score` is relevance, but can be null when sorting
by another field.

## ES semantics: edit `pink_house_knn.json`

Change `encode.text` to your natural-language query. Set `search.knn.k` and
`search.size` to the desired result count. `search.knn.num_candidates` controls
the approximate candidate pool per shard: larger is usually more accurate but
slower; keep it greater than `k`, at most 10,000.

Leave `query_vector` empty: the commands fill it from Qwen. `encode` and `search`
are our file's wrappers; the commands send them to their respective services.
For restrictions, add a `filter` **inside `search.knn`**, for example
`"filter": {"range": {"date": {"gte": "2025-01-01"}}}`.
Only vectorised reviews participate. See [ES kNN](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/knn-search.html).

## Project rules to remember

- Accommodation has no canonical price field: prices live in `price_quotes`.
  Reading its history directly does not apply `latest-valid` or `agreement-only`.
- Stored owner status is a dated snapshot. Native reads do not recalculate expiry
  for today; check the reference dates or use the project's owner-status functions.
- JSON requires double quotes and no comments or trailing commas. Change values
  and clauses, keeping the example's surrounding braces and commas valid.
