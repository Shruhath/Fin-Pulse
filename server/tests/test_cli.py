import json

import pytest

from finpulse import cli
from finpulse.api.app import app


def test_every_command_parses_and_has_help():
    parser = cli.build_parser()
    for argv in (
        ["status"], ["gazetteer"], ["ingest", "rbi"], ["parse", "--redo"], ["link", "--relink"], ["events"],
        ["sentiment", "train", "--model", "finbert", "--epochs", "2"], ["sentiment", "score"],
        ["pipeline", "--stages", "parse", "link"], ["llm"], ["gold", "select", "--quota", "A=1,B=2"],
        ["gold", "import", "export.json", "--annotators", "1=a"], ["export", "--include-text"],
        ["openapi", "--check"], ["embed"], ["worker", "--once"], ["serve"],
    ):  # fmt: skip
        assert parser.parse_args(argv).fn is not None


def test_unknown_stages_and_models_are_rejected_by_the_parser():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["sentiment", "train", "--model", "gpt"])
    with pytest.raises(SystemExit):
        parser.parse_args(["gold", "frobnicate"])


def test_quota_parsing():
    assert cli._parse_quotas("SEBI adjudication order=40, NCLT admission order=50") == {
        "SEBI adjudication order": 40,
        "NCLT admission order": 50,
    }
    assert cli._parse_quotas(None) is None


def test_the_committed_openapi_document_matches_the_app(tmp_path, capsys):
    out = tmp_path / "openapi.json"
    assert cli.main(["openapi", "--out", str(out), "--check"]) == 1  # missing file: out of date
    cli.main(["openapi", "--out", str(out)])
    assert cli.main(["openapi", "--out", str(out), "--check"]) == 0
    spec = json.loads(out.read_text())
    assert (
        spec["info"]["title"] == "FinPulse API"
        and "/api/summaries" in spec["paths"]
        and "/api/search" in spec["paths"]
    )
    assert spec == json.loads(json.dumps(app.openapi(), sort_keys=True))
