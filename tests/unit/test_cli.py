import pytest

from mcp_bigquery_evals.cli import main


def test_cli_help_exits_clean(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "serve" in captured.out
    assert "evals" in captured.out


def test_cli_evals_stub_returns_nonzero(capsys):
    rc = main(["evals"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Plan B" in captured.err
