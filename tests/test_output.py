import gzip
import io
import sys
from pathlib import Path

import pandas as pd
import pytest

from zendt.engine.input import resolve_input
from zendt.engine.output import write_output


class Stdout(io.StringIO):
    def __init__(self, tty: bool = False) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_write_output_keeps_the_input_delimiter(tmp_path: Path):
    source = tmp_path / 'in.csv'
    source.write_text('valor;nome\n1.234,56;foo\n', encoding='utf-8')
    frame = resolve_input(str(source))
    target = tmp_path / 'out.csv'

    write_output(frame, str(target))

    assert target.read_text(encoding='utf-8') == 'valor;nome\n1.234,56;foo\n'


def test_write_output_gzip_keeps_the_input_delimiter(tmp_path: Path):
    source = tmp_path / 'in.csv'
    source.write_text('amount,code\n10,a\n', encoding='utf-8')
    frame = resolve_input(str(source))
    target = tmp_path / 'out.csv.gz'

    write_output(frame, str(target))

    with gzip.open(target, 'rt', encoding='utf-8') as handle:
        assert handle.read() == 'amount,code\n10,a\n'


def test_write_output_stdout_uses_the_input_delimiter(
    capsys: pytest.CaptureFixture[str],
):
    frame = pd.DataFrame([{'valor': '1.234,56', 'nome': 'foo'}])
    frame.attrs['delimiter'] = ';'

    write_output(frame, None)

    assert capsys.readouterr().out == 'valor;nome\n1.234,56;foo\n'


def test_write_output_json_and_excel(tmp_path: Path):
    frame = pd.DataFrame([{'amount': 1, 'code': 'á'}])
    frame.attrs['delimiter'] = ','
    json_path = tmp_path / 'out.json'
    excel_path = tmp_path / 'out.xlsx'

    write_output(frame, str(json_path))
    write_output(frame, str(excel_path))

    assert json_path.read_text(encoding='utf-8') == '[{"amount":1,"code":"á"}]'
    assert pd.read_excel(excel_path)['code'].tolist() == ['á']


def test_write_output_rejects_an_unsupported_format(tmp_path: Path):
    frame = pd.DataFrame([{'amount': 1}])
    with pytest.raises(Exception, match='not supported'):
        write_output(frame, str(tmp_path / 'out.parquet'))


def test_write_output_skips_a_terminal(monkeypatch: pytest.MonkeyPatch):
    frame = pd.DataFrame([{'amount': 1, 'code': 'a'}])
    frame.attrs['delimiter'] = ','
    stdout = Stdout(tty=True)
    monkeypatch.setattr(sys, 'stdout', stdout)

    write_output(frame, None)

    assert stdout.getvalue() == ''
