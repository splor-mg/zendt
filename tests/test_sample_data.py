"""Apply sample_rules to the shared fixtures under tests/data."""

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from zendt.cli import app
from zendt.engine import evaluate
from zendt.engine.input import resolve_input

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
RULES = ROOT / 'sample_rules'
FINANCE_CSV = DATA / 'synthetic_personal_finance_dataset.csv'

runner = CliRunner()


def combined(result) -> str:
    text = f'{result.stdout or ""}{result.stderr or ""}'
    return text or (result.output or '')


def write_head(source: Path, destination: Path, n_rows: int = 25) -> None:
    """Copy the header and the first `n_rows` of data.

    Keeps the delimiter and BOM as in the file.
    """
    with source.open('r', encoding='utf-8', newline='') as handle:
        lines = [handle.readline() for _ in range(n_rows + 1)]
    destination.write_text(''.join(lines), encoding='utf-8')


def test_sample_rules_are_listed():
    result = runner.invoke(app, ['list', '-s', str(RULES)])
    assert result.exit_code == 0, combined(result)
    assert 'finance_rule' in combined(result)


def test_apply_finance_rule_on_synthetic_finance(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sample = tmp_path / 'finance_sample.csv'
    write_head(FINANCE_CSV, sample, n_rows=30)
    out = tmp_path / 'finance_out.csv'

    result = runner.invoke(
        app,
        [
            'apply',
            'finance_rule',
            '-s',
            str(RULES),
            '-i',
            str(sample),
            '-o',
            str(out),
        ],
    )
    assert result.exit_code == 0, combined(result)
    evaluate.close_pool()

    frame = resolve_input(str(out))
    assert 'disposable_income_usd' in frame.columns
    assert 'is_high_credit' in frame.columns
    assert len(frame) == 30
    expected = (
        frame['monthly_income_usd'] - frame['monthly_expenses_usd']
    ).round(6)
    assert (
        frame['disposable_income_usd'].round(6).tolist() == expected.tolist()
    )


def test_sample_data_files_exist_and_have_expected_columns():
    assert FINANCE_CSV.is_file()
    finance = pd.read_csv(FINANCE_CSV, nrows=1)
    for column in (
        'monthly_income_usd',
        'monthly_expenses_usd',
        'credit_score',
    ):
        assert column in finance.columns
