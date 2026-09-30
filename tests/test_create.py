import json
from pathlib import Path

import typer

from zendt.config.create import create_config


class Script:
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


def run_create(monkeypatch, script: Script) -> None:
    monkeypatch.setattr(typer, 'prompt', script.prompt)
    monkeypatch.setattr(typer, 'confirm', script.confirm)
    create_config()
    assert script.prompts == []
    assert script.confirms == []


def test_create_local_source_and_flow(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_create(
        monkeypatch,
        Script(
            [
                'local_rules',
                'home/rules',
                'score',
                'adds a score',
                'flag, other',
            ],
            [False, True, False, False, False],
        ),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved == {
        'sources': [{'id': 'local_rules', 'source': 'home/rules'}],
        'flows': [
            {
                'id': 'score',
                'description': 'adds a score',
                'rules': ['flag', 'other'],
            }
        ],
    }


def test_create_private_source_with_version(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_create(
        monkeypatch,
        Script(
            [
                'remote_rules',
                'https://github.com/user/repo',
                'GH_TOKEN',
                '1.2.1',
                'score',
                'remote flow',
                'flag',
                'data/in.csv',
                'data/out.csv',
            ],
            [True, True, False, True, True, True, False],
        ),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved['sources'] == [
        {
            'id': 'remote_rules',
            'source': 'https://github.com/user/repo',
            'authentication': 'GH_TOKEN',
            'version': '1.2.1',
        }
    ]
    assert saved['flows'][0]['input'] == 'data/in.csv'
    assert saved['flows'][0]['output'] == 'data/out.csv'


def test_create_overwrites_when_confirmed(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'zendt.json').write_text('{"keep": true}', encoding='utf-8')
    run_create(
        monkeypatch,
        Script(
            ['local_rules', 'home/rules', 'score', 'note', 'flag'],
            [True, False, True, False, False, False],
        ),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved['sources'][0]['id'] == 'local_rules'


def test_create_source_without_flow(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_create(
        monkeypatch,
        Script(['local_rules', 'home/rules'], [False, False]),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved == {
        'sources': [{'id': 'local_rules', 'source': 'home/rules'}],
        'flows': [],
    }


def test_create_asks_again_for_a_bad_source_id(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_create(
        monkeypatch,
        Script(
            ['bad/id', 'home/rules', 'local_rules', 'home/rules'],
            [False, False],
        ),
    )
    saved = json.loads((tmp_path / 'zendt.json').read_text(encoding='utf-8'))
    assert saved['sources'] == [{'id': 'local_rules', 'source': 'home/rules'}]


def test_create_refuses_to_overwrite(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / 'zendt.json'
    path.write_text('{"keep": true}', encoding='utf-8')
    run_create(monkeypatch, Script([], [False]))
    assert path.read_text(encoding='utf-8') == '{"keep": true}'
