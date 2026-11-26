import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from psycopg.rows import dict_row
from starlette.concurrency import run_in_threadpool

from llm_log_summary import parse_lines

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
MAX_BODY = 2_000_000
WINDOWS = {"15m": 900, "1h": 3600, "24h": 86400, "7d": 604800}


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


@asynccontextmanager
async def lifespan(app):
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY, model TEXT NOT NULL,
                occurred_at TIMESTAMPTZ NOT NULL, latency_ms BIGINT NOT NULL,
                input_tokens BIGINT NOT NULL, output_tokens BIGINT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS requests_time_idx ON requests (occurred_at)")
    yield


app = FastAPI(title="LLM Request Monitor", lifespan=lifespan)


def import_records(body):
    result = {"inserted": 0, "duplicates": 0, "rejected": []}
    with connect() as db:
        for line in parse_lines(body.splitlines()):
            record = line.record
            error = line.error
            if error is None:
                try:
                    timestamp = datetime.fromisoformat(record["occurred_at"].replace("Z", "+00:00"))
                    if timestamp.utcoffset() is None:
                        raise ValueError
                except (KeyError, AttributeError, ValueError):
                    error = "occurred_at must be an ISO 8601 timestamp with a timezone"
                if any(record[field] > 2**63 - 1 for field in ("latency_ms", "input_tokens", "output_tokens")):
                    error = "numeric values exceed the database integer limit"
                for field in ("model", "request_id"):
                    try:
                        record[field].encode("utf-8")
                    except UnicodeEncodeError:
                        error = f"{field} must be valid Unicode"
                    if "\x00" in record[field] or len(record[field].encode("utf-8", errors="replace")) > 256:
                        error = f"{field} must be at most 256 UTF-8 bytes and contain no nulls"
            if error:
                result["rejected"].append({"line": line.number, "error": error})
                continue
            record["occurred_at"] = timestamp
            inserted = db.execute("""
                INSERT INTO requests VALUES (
                    %(request_id)s, %(model)s, %(occurred_at)s, %(latency_ms)s,
                    %(input_tokens)s, %(output_tokens)s, %(status)s
                ) ON CONFLICT (request_id) DO NOTHING
            """, record).rowcount
            result["inserted" if inserted else "duplicates"] += 1
    return result


@app.post("/api/import")
async def import_logs(request: Request):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BODY:
            raise HTTPException(413, "Import must be at most 2 MB")
        data.extend(chunk)
    try:
        body = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "Import must be UTF-8") from exc
    return await run_in_threadpool(import_records, body)


def metrics(window):
    with connect() as db:
        return db.execute("""
            SELECT model, count(*) AS requests,
                   count(*) FILTER (WHERE status = 'error')::float / count(*) AS error_rate,
                   percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms
            FROM requests
            WHERE occurred_at BETWEEN now() - %s * interval '1 second' AND now()
            GROUP BY model ORDER BY p95_ms DESC, model
        """, (WINDOWS[window],)).fetchall()


Window = Literal["15m", "1h", "24h", "7d"]


@app.get("/api/metrics")
def get_metrics(window: Window = "1h"):
    return metrics(window)


@app.get("/")
def dashboard(request: Request, window: Window = "1h"):
    return templates.TemplateResponse(request=request, name="dashboard.html",
                                      context={"rows": metrics(window), "window": window, "windows": WINDOWS})
