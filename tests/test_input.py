import gzip
import io
import json
from pathlib import Path

import pandas as pd
import pytest

from zendt.engine.input import resolve_input
from zendt.errors import InputError


class Stdin(io.StringIO):
    def __init__(self, text: str, tty: bool = False) -> None:
        super().__init__(text)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_resolve_input_reads_csv(tmp_path: Path):
    path = tmp_path / 'rows.csv'
    path.write_text('amount,code\n10,a\n20,b\n', encoding='utf-8')

    frame = resolve_input(str(path))

    assert list(frame.columns) == ['amount', 'code']
    assert frame['amount'].tolist() == [10, 20]
    assert frame.attrs['delimiter'] == ','


def test_resolve_input_reads_semicolon_csv(tmp_path: Path):
    path = tmp_path / 'rows.csv'
    path.write_text('valor;nome\n1.234,56;foo\n', encoding='utf-8')

    frame = resolve_input(str(path))

    assert list(frame.columns) == ['valor', 'nome']
    assert frame['valor'].tolist() == ['1.234,56']
    assert frame.attrs['delimiter'] == ';'


def test_resolve_input_reads_csv_gz(tmp_path: Path):
    path = tmp_path / 'rows.csv.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as handle:
        handle.write('amount\n5\n')

    frame = resolve_input(str(path))

    assert frame['amount'].tolist() == [5]


def test_resolve_input_json_array_and_object(tmp_path: Path):
    rows = tmp_path / 'rows.json'
    rows.write_text(
        json.dumps([{'amount': 1}, {'amount': 2}]), encoding='utf-8'
    )
    one = tmp_path / 'one.json'
    one.write_text(json.dumps({'amount': 9}), encoding='utf-8')

    assert resolve_input(str(rows))['amount'].tolist() == [1, 2]
    assert resolve_input(str(one))['amount'].tolist() == [9]


def test_resolve_input_reads_excel(tmp_path: Path):
    path = tmp_path / 'rows.xlsx'
    pd.DataFrame([{'amount': 3}]).to_excel(path, index=False)

    frame = resolve_input(str(path))

    assert frame['amount'].tolist() == [3]


def test_resolve_input_rejects_unknown_format(tmp_path: Path):
    path = tmp_path / 'rows.txt'
    path.write_text('amount\n1\n', encoding='utf-8')

    with pytest.raises(InputError, match='not supported'):
        resolve_input(str(path))


def test_resolve_input_rejects_json_that_is_not_rows(tmp_path: Path):
    path = tmp_path / 'rows.json'
    path.write_text('[1, 2, 3]', encoding='utf-8')

    with pytest.raises(InputError, match='array of objects'):
        resolve_input(str(path))


def test_stdin_csv_and_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('sys.stdin', Stdin('amount;code\n4;a\n'))
    frame = resolve_input(None)
    assert frame['amount'].tolist() == [4]
    assert frame.attrs['delimiter'] == ';'

    monkeypatch.setattr('sys.stdin', Stdin('[{"amount": 7}]'))
    assert resolve_input(None)['amount'].tolist() == [7]


def test_stdin_invalid_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('sys.stdin', Stdin('{not json'))
    with pytest.raises(InputError, match='invalid'):
        resolve_input(None)


def test_unreadable_input_path(tmp_path: Path):
    with pytest.raises(InputError, match='Could not read'):
        resolve_input(str(tmp_path / 'missing.csv'))


def test_stdin_empty_or_tty_is_an_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('sys.stdin', Stdin(''))
    with pytest.raises(InputError, match='empty'):
        resolve_input(None)

    monkeypatch.setattr('sys.stdin', Stdin('', tty=True))
    with pytest.raises(InputError, match='No input'):
        resolve_input(None)
