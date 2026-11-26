"""Print an incident demo as JSON Lines with timestamps relative to now."""
import json
from datetime import datetime, timedelta, timezone


def incident():
    now = datetime.now(timezone.utc)
    for model, base in (("aurora-small", 240), ("aurora-large", 510)):
        for index in range(48):
            spike = model == "aurora-large" and index >= 39
            yield {
                "request_id": f"demo-{model}-{index}", "model": model,
                "occurred_at": (now - timedelta(minutes=48 - index)).isoformat(),
                "latency_ms": (2900 if spike else base) + (index % 8) * 19,
                "input_tokens": 250, "output_tokens": 0 if spike and index % 3 == 0 else 90,
                "status": "error" if spike and index % 3 == 0 else "ok",
            }


if __name__ == "__main__":
    for record in incident():
        print(json.dumps(record))
