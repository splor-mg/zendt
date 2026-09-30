from pathlib import Path

import pytest

from zendt.engine.helpers import detect_delimiter, type_of_file
from zendt.errors import InputError
from zendt.rules.check_jdm import rule_children, validate_jdm


def test_detect_delimiter_comma_semicolon_and_fallback():
    assert detect_delimiter('a,b\n1,2\n') == ','
    assert detect_delimiter('a;b\n1;2\n') == ';'
    assert detect_delimiter('') == ','


def test_type_of_file_known_and_unknown(tmp_path: Path):
    assert type_of_file(str(tmp_path / 'rows.CSV.GZ')) == '.csv.gz'
    assert type_of_file(str(tmp_path / 'rows.xlsx')) == '.xlsx'
    with pytest.raises(InputError, match='not supported'):
        type_of_file(str(tmp_path / 'rows.xls'))
    with pytest.raises(InputError, match='not supported'):
        type_of_file(str(tmp_path / 'rows.parquet'))


def test_validate_jdm_and_children():
    assert validate_jdm({'nodes': [], 'edges': []})
    assert not validate_jdm({'nodes': []})
    assert not validate_jdm([])
    graph = {
        'nodes': [
            {'type': 'inputNode'},
            {'type': 'decisionNode', 'content': {'key': 'child/rule'}},
            {'type': 'expressionNode', 'content': {'key': 'ignored'}},
        ],
        'edges': [],
    }
    assert rule_children(graph) == ['child/rule']
