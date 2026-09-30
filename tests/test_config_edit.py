import json
from pathlib import Path

import typer

from zendt.config.edit import edit_config

SAMPLE = {
    'sources': [
        {
            'id': 'source_one',
            'source': 'https://github.com/user/rules_repo.git',
            'authentication': 'GH_TOKEN',
            'version': '1.0.0',
        },
        {
            'id': 'source_two',
            'source': 'home/sample/rules',
        },
    ],
    'flows': [
        {
            'id': 'financedata',
            'description': 'finance team flow',
            'input': 'data-raw/finance.csv.gz',
            'rules': ['student_discount', 'age_discount'],
            'output': 'data/finance.csv',
        }
    ],
}


class Script:
    """Feed prompt/confirm answers.

    None means press enter (use the default).
    """

    def __init__(
        self, prompts: list[str | None], confirms: list[bool] | None = None
    ) -> None:
        self.prompts = list(prompts)
        self.confirms = list(confirms or [])

    def prompt(
        self, text: str = '', default: str | None = None, **kwargs: object
    ) -> str:
        if not self.prompts:
            raise AssertionError(f'unexpected prompt: {text}')
        answer = self.prompts.pop(0)
        if answer is None:
            return '' if default is None else default
        return answer

    def confirm(self, text: str = '', **kwargs: object) -> bool:
        if not self.confirms:
            raise AssertionError(f'unexpected confirm: {text}')
        return self.confirms.pop(0)


def write_config(directory: Path, data: dict | None = None) -> Path:
    path = directory / 'zendt.json'
    path.write_text(
        json.dumps(data if data is not None else SAMPLE), encoding='utf-8'
    )
    return path


def run_edit(monkeypatch, script: Script) -> None:
    monkeypatch.setattr(typer, 'prompt', script.prompt)
    monkeypatch.setattr(typer, 'confirm', script.confirm)
    edit_config()
    assert script.prompts == []
    assert script.confirms == []


def test_edit_source_updates_remote_fields(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script([
            '1',
            '3',
            'source_one',
            'https://github.com/user/other.git',
            'OTHER_TOKEN',
            '2.0.0',
            '3',
        ]),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    source = saved['sources'][0]
    assert source['source'] == 'https://github.com/user/other.git'
    assert source['authentication'] == 'OTHER_TOKEN'
    assert source['version'] == '2.0.0'


def test_enter_keeps_current_source_values(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script(['1', '3', 'source_one', None, None, None, '3']),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved['sources'][0] == SAMPLE['sources'][0]


def test_local_source_drops_authentication_and_version(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script(['1', '3', 'source_one', 'home/rules', '3']),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    source = saved['sources'][0]
    assert source == {'id': 'source_one', 'source': 'home/rules'}


def test_clear_optional_source_fields(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script(['1', '3', 'source_one', None, '-', '-', '3']),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    source = saved['sources'][0]
    assert source == {
        'id': 'source_one',
        'source': 'https://github.com/user/rules_repo.git',
    }


def test_delete_source_keeps_the_last_one(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(
        tmp_path,
        {'sources': [{'id': 'only', 'source': 'home/rules'}], 'flows': []},
    )
    run_edit(monkeypatch, Script(['1', '2', 'only', '3']))
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert [source['id'] for source in saved['sources']] == ['only']


def test_delete_source(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch, Script(['1', '2', 'source_two', '3'], confirms=[True])
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert [source['id'] for source in saved['sources']] == ['source_one']


def test_create_local_source(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script(['1', '1', 'local_rules', 'home/rules', '3']),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved['sources'][-1] == {
        'id': 'local_rules',
        'source': 'home/rules',
    }


def test_duplicate_source_is_not_added(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script(['1', '1', 'source_one', 'home/other', '3']),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert [source['id'] for source in saved['sources']] == [
        'source_one',
        'source_two',
    ]


def test_edit_flow_and_clear_paths(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script([
            '2',
            '3',
            'financedata',
            'updated description',
            'student_discount',
            '-',
            '-',
            '3',
        ]),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved['flows'] == [
        {
            'id': 'financedata',
            'description': 'updated description',
            'rules': ['student_discount'],
        }
    ]


def test_create_flow_stores_paths(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script(
            [
                '2',
                '1',
                'receita',
                'regras de receita',
                'is_asps_rec, is_impostos',
                'data/input.csv',
                'data/output.csv',
                '3',
            ],
            confirms=[True, True],
        ),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved['flows'][-1] == {
        'id': 'receita',
        'description': 'regras de receita',
        'rules': ['is_asps_rec', 'is_impostos'],
        'input': 'data/input.csv',
        'output': 'data/output.csv',
    }


def test_invalid_choice_then_back_and_delete_flow(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script(['9', '2', '4', '2', '2', 'financedata', '3'], confirms=[True]),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved['flows'] == []


def test_unknown_ids_and_invalid_new_entries_are_rejected(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    run_edit(
        monkeypatch,
        Script(
            [
                '1',
                '3',
                'missing',
                '1',
                '1',
                'bad/id',
                'home/rules',
                '2',
                '1',
                'financedata',
                'duplicate',
                ',',
                '2',
                '3',
                'missing-flow',
                '3',
            ],
            confirms=[False, False],
        ),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert [source['id'] for source in saved['sources']] == [
        'source_one',
        'source_two',
    ]
    assert [flow['id'] for flow in saved['flows']] == ['financedata']


def test_broken_config_file_is_not_rewritten(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / 'zendt.json'
    path.write_text('{', encoding='utf-8')
    edit_config()
    assert 'Error loading' in capsys.readouterr().out
    assert path.read_text(encoding='utf-8') == '{'


def test_missing_config_file(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    edit_config()
    captured = capsys.readouterr()
    assert 'zendt config --create' in captured.out
    assert not (tmp_path / 'zendt.json').exists()
