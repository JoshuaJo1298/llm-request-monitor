"""Summarise LLM request logs from a JSON Lines file."""
import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional


@dataclass
class ParsedLine:
    number: int
    record: Optional[dict] = None
    error: Optional[str] = None


def validate_record(record):
    if not isinstance(record, dict):
        return "record must be a JSON object"
    text_fields = ("request_id", "model")
    numbers = ("latency_ms", "input_tokens", "output_tokens")
    missing = [field for field in (*text_fields, *numbers, "status") if field not in record]
    if missing:
        return "missing fields: " + ", ".join(missing)
    for field in text_fields:
        if not isinstance(record[field], str) or not record[field].strip():
            return f"{field} must be a non-empty string"
    if record["status"] not in ("ok", "error"):
        return "status must be ok or error"
    for field in numbers:
        if type(record[field]) is not int or record[field] < 0:
            return f"{field} must be a non-negative integer"
    return None


def parse_lines(lines: Iterable[str]) -> Iterator[ParsedLine]:
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            yield ParsedLine(number, error=f"invalid JSON: {exc}")
            continue
        error = validate_record(record)
        yield ParsedLine(number, record if error is None else None, error)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="path to a JSON Lines file")
    args = parser.parse_args(argv)
    counts = defaultdict(lambda: [0, 0, 0, 0, 0])
    try:
        with open(args.path, encoding="utf-8", errors="replace") as handle:
            for line in parse_lines(handle):
                if line.error:
                    print(f"line {line.number}: {line.error}", file=sys.stderr)
                    continue
                record = line.record
                totals = counts[record["model"]]
                totals[0] += 1
                totals[1] += record["status"] == "error"
                totals[2] += record["latency_ms"]
                totals[3] += record["input_tokens"]
                totals[4] += record["output_tokens"]
    except OSError as exc:
        print(f"error: cannot read {args.path!r}: {exc.strerror or exc}", file=sys.stderr)
        return 1

    summary = {
        model: dict(request_count=count, failure_rate=errors / count,
                    mean_latency_ms=latency / count, total_input_tokens=inputs,
                    total_output_tokens=outputs)
        for model, (count, errors, latency, inputs, outputs) in counts.items()
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
