import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from zendt import apply as apply_rules
from zendt.cli import app
from zendt.engine import evaluate

runner = CliRunner()


def score_graph(column: str = 'scored') -> dict:
    return {
        'nodes': [
            {'id': 'input', 'name': 'Request', 'type': 'inputNode'},
            {
                'id': 'expr',
                'name': 'score',
                'type': 'expressionNode',
                'content': {
                    'expressions': [
                        {'id': 'e', 'key': column, 'value': 'amount + 1'}
                    ],
                },
            },
            {'id': 'output', 'name': 'Response', 'type': 'outputNode'},
        ],
        'edges': [
            {'id': 'e1', 'sourceId': 'input', 'targetId': 'expr'},
            {'id': 'e2', 'sourceId': 'expr', 'targetId': 'output'},
        ],
    }


def write_rule(directory: Path, name: str, column: str = 'scored') -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f'{name}.json').write_text(
        json.dumps(score_graph(column)), encoding='utf-8'
    )


def combined(result) -> str:
    text = f'{result.stdout or ""}{result.stderr or ""}'
    return text or (result.output or '')


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    text = combined(result)
    assert 'apply' in text
    assert 'flow' in text
    assert 'list' in text


def test_version_flag():
    result = runner.invoke(app, ['-V'])
    assert result.exit_code == 0
    assert combined(result).strip() == 'zendt 0.1.0'


def test_list_prints_rule_names(tmp_path: Path):
    write_rule(tmp_path, 'is_asps')
    write_rule(tmp_path, 'is_mde', 'other')
    result = runner.invoke(app, ['list', '-s', str(tmp_path)])
    assert result.exit_code == 0
    text = combined(result)
    assert 'is_asps' in text
    assert 'is_mde' in text


def test_list_find_filters_and_reports_no_match(tmp_path: Path):
    write_rule(tmp_path, 'is_asps')
    found = runner.invoke(app, ['list', '-s', str(tmp_path), '-f', 'asps'])
    assert found.exit_code == 0
    assert 'is_asps' in combined(found)

    missing = runner.invoke(app, ['list', '-s', str(tmp_path), '-f', 'nope'])
    assert missing.exit_code == 1
    assert 'No rules matching' in combined(missing)


def test_apply_writes_the_new_column(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_rule(tmp_path, 'flag')
    (tmp_path / 'in.csv').write_text('amount\n10\n', encoding='utf-8')

    result = runner.invoke(
        app,
        [
            'apply',
            'flag',
            '-s',
            str(tmp_path),
            '-i',
            'in.csv',
            '-o',
            'out.csv',
        ],
    )

    assert result.exit_code == 0, combined(result)
    assert (tmp_path / 'out.csv').read_text(
        encoding='utf-8'
    ) == 'amount,scored\n10,11\n'
    evaluate.close_pool()


def test_apply_rejects_a_rules_flag(tmp_path: Path):
    result = runner.invoke(app, ['apply', '-r', 'flag', '-s', str(tmp_path)])
    assert result.exit_code != 0
    assert 'No such option' in combined(result)


def test_apply_missing_rule_exits_with_the_error(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_rule(tmp_path, 'flag')
    (tmp_path / 'in.csv').write_text('amount\n1\n', encoding='utf-8')
    result = runner.invoke(
        app, ['apply', 'missing', '-s', str(tmp_path), '-i', 'in.csv']
    )
    assert result.exit_code == 1
    assert 'not found' in combined(result)


def test_apply_without_input_fails_on_a_terminal(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_rule(tmp_path, 'flag')
    result = runner.invoke(app, ['apply', 'flag', '-s', str(tmp_path)])
    assert result.exit_code == 1
    assert 'Stdin is empty' in combined(result)


def test_apply_head_previews_without_replacing_the_file(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    write_rule(tmp_path, 'flag')
    (tmp_path / 'in.csv').write_text('amount\n10\n20\n', encoding='utf-8')
    result = runner.invoke(
        app,
        [
            'apply',
            'flag',
            '-s',
            str(tmp_path),
            '-i',
            'in.csv',
            '-o',
            'out.csv',
            '--printhead',
        ],
    )
    assert result.exit_code == 0, combined(result)
    assert 'scored' in combined(result)
    assert (
        (tmp_path / 'out.csv')
        .read_text(encoding='utf-8')
        .startswith('amount,scored\n')
    )
    evaluate.close_pool()


def test_flow_uses_config_and_flag_overrides(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rules = tmp_path / 'rules'
    write_rule(rules, 'flag')
    (tmp_path / 'in.csv').write_text('amount\n3\n', encoding='utf-8')
    (tmp_path / 'zendt.json').write_text(
        json.dumps({
            'sources': [{'id': 'rules', 'source': 'rules'}],
            'flows': [
                {'id': 'score', 'rules': ['flag'], 'input': 'missing.csv'}
            ],
        }),
        encoding='utf-8',
    )

    result = runner.invoke(
        app, ['flow', 'score', '-i', 'in.csv', '-o', 'out.csv']
    )

    assert result.exit_code == 0, combined(result)
    frame = pd.read_csv(tmp_path / 'out.csv')
    assert frame['scored'].tolist() == [4]
    evaluate.close_pool()


def test_flow_writes_the_configured_output(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rules = tmp_path / 'rules'
    write_rule(rules, 'flag')
    (tmp_path / 'in.csv').write_text('amount\n3\n', encoding='utf-8')
    (tmp_path / 'zendt.json').write_text(
        json.dumps({
            'sources': [{'id': 'rules', 'source': 'rules'}],
            'flows': [
                {
                    'id': 'score',
                    'rules': ['flag'],
                    'input': 'in.csv',
                    'output': 'from-config.csv',
                }
            ],
        }),
        encoding='utf-8',
    )

    result = runner.invoke(app, ['flow', 'score'])

    assert result.exit_code == 0, combined(result)
    frame = pd.read_csv(tmp_path / 'from-config.csv')
    assert frame['scored'].tolist() == [4]
    evaluate.close_pool()


def test_apply_from_python_accepts_a_dataframe(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_rule(tmp_path, 'flag')

    result = apply_rules(
        ['flag'],
        source=str(tmp_path),
        input=pd.DataFrame({'amount': [10]}),
    )

    assert result['scored'].tolist() == [11]
    evaluate.close_pool()


def test_flow_unknown_id(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'zendt.json').write_text(
        json.dumps({
            'sources': [
                {'id': 'rules', 'source': 'https://github.com/user/repo'}
            ],
            'flows': [{'id': 'score', 'rules': ['flag']}],
        }),
        encoding='utf-8',
    )
    result = runner.invoke(app, ['flow', 'missing'])
    assert result.exit_code == 1
    assert 'not found' in combined(result)


def test_config_flags_call_create_before_edit(monkeypatch):
    called = []
    monkeypatch.setattr(
        'zendt.cli.create_config', lambda: called.append('create')
    )
    monkeypatch.setattr('zendt.cli.edit_config', lambda: called.append('edit'))

    created = runner.invoke(app, ['config', '--create'])
    edited = runner.invoke(app, ['config', '--edit'])
    both = runner.invoke(app, ['config', '--create', '--edit'])

    assert created.exit_code == edited.exit_code == both.exit_code == 0
    assert called == ['create', 'edit', 'create']


def test_config_without_flags_does_nothing(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ['config'])
    assert result.exit_code == 0
    assert not (tmp_path / 'zendt.json').exists()


def test_list_from_zendt_json_prints_qualified_names(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    rules = tmp_path / 'rules'
    write_rule(rules, 'flag')
    (tmp_path / 'zendt.json').write_text(
        json.dumps({
            'sources': [{'id': 'rules', 'source': 'rules'}],
            'flows': [],
        }),
        encoding='utf-8',
    )
    result = runner.invoke(app, ['list'])
    assert result.exit_code == 0
    assert 'rules/flag' in combined(result)
