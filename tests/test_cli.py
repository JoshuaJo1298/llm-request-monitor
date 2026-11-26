import json

from llm_log_summary import main


def test_mixed_sample(capsys):
    assert main(["sample.jsonl"]) == 0
    output = capsys.readouterr()
    summary = json.loads(output.out)
    assert summary["model-a"] == {
        "request_count": 2, "failure_rate": 0.5, "mean_latency_ms": 300,
        "total_input_tokens": 220, "total_output_tokens": 40,
    }
    assert summary["model-b"]["request_count"] == 1
    assert "line 3:" in output.err


def test_invalid_and_empty(tmp_path, capsys):
    path = tmp_path / "logs"
    path.write_text('{"request_id":"id","model":"m","status":[],'
                    '"latency_ms":false,"input_tokens":0,"output_tokens":0}\n\n')
    assert main([str(path)]) == 0
    output = capsys.readouterr()
    assert output.out.strip() == "{}"
    assert "line 1:" in output.err
    path.write_text("")
    assert main([str(path)]) == 0
    assert capsys.readouterr().out.strip() == "{}"
    assert main([str(tmp_path / "missing")]) == 1
