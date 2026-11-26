# LLM Request Monitor

Inspect request volume, error rate and p95 latency by model. FastAPI serves the dashboard and the import API. PostgreSQL stores request metadata and calculates aggregates.

## Run the incident demo

Requires Python 3.9+ and Docker Compose, or an existing PostgreSQL database.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d
export DATABASE_URL=postgresql://monitor:monitor@localhost:5432/monitor
uvicorn app:app
```

In a second terminal, from this project directory:

```sh
python3 seed.py > /tmp/monitor-incident.jsonl
curl -fsS --data-binary @/tmp/monitor-incident.jsonl http://localhost:8000/api/import
curl -fsS http://localhost:8000/api/metrics
```

Open http://localhost:8000. The last hour shows 48 calls per model, with 6.2% errors and 3,014 ms p95 for `aurora-large`. Set the window to 15 minutes to focus on the spike. Re-submit the same file to see 96 duplicates and unchanged totals. The seed uses stable IDs and relative timestamps. Point the demo at a fresh database to repeat it at a later date. [Recorded demo](demo.md)

## Import and tests

`POST /api/import` accepts up to 2 MB of UTF-8 JSONL. Each record uses the CLI fields plus `occurred_at`, an ISO 8601 timestamp with a timezone. The response includes inserted and duplicate counts plus errors with one-based line numbers. Existing request IDs keep their original record. The CLI can also process files without timestamps.

```sh
python llm_log_summary.py sample.jsonl
pip install pytest httpx
TEST_DATABASE_URL="$DATABASE_URL" python -m pytest -q
```

Using the request ID as a unique key lets PostgreSQL enforce deduplication even when imports overlap. The tradeoff is that a producer must generate globally unique IDs. The dashboard computes exact, discrete p95 on demand for the selected time window. For a larger log volume, measure query costs before choosing a pre-aggregation strategy.

The app is designed for local use with synthetic request metadata.
