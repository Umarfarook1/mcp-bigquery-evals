import pytest

from mcp_bigquery_evals.cli import main


def test_cli_help_exits_clean(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "serve" in captured.out
    assert "evals" in captured.out


def test_cli_evals_without_subcommand_prints_hint(capsys) -> None:
    rc = main(["evals"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "evals run" in captured.err


def test_cli_evals_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["evals", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "run" in captured.out


def test_cli_evals_run_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["evals", "run", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "--model" in captured.out
    assert "--golden" in captured.out
    assert "--limit" in captured.out
    assert "--report" in captured.out
