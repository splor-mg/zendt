import json
from pathlib import Path

import pytest

from zendt.errors import ConfigError
from zendt.rules.configs import (
    find_config,
    get_flow,
    get_source,
    load_config,
    load_default_config,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / 'zendt_sample.json'

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
            'description': 'finance team flow for discount purposes',
            'input': './data-raw/finance.csv.gz',
            'rules': ['student_discount', 'age_discount', 'other_discount'],
            'output': './data/finance.csv',
        }
    ],
}


def write_config(directory: Path, data: dict) -> Path:
    path = directory / 'zendt.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def test_load_repo_zendt_json():
    config = load_config(SAMPLE_PATH)
    assert [source.id for source in config.sources] == [
        'source_one',
        'source_two',
    ]
    assert get_source(config, 'source_one').authentication == 'GH_TOKEN'
    assert get_flow(config, 'financedata').rules == [
        'student_discount',
        'age_discount',
        'other_discount',
    ]


def test_optional_source_fields(tmp_path: Path):
    config = load_config(write_config(tmp_path, SAMPLE))
    source_two = get_source(config, 'source_two')
    assert source_two.authentication is None
    assert source_two.version is None


def test_relative_paths_resolve_against_config_dir(tmp_path: Path):
    config = load_config(write_config(tmp_path, SAMPLE))
    assert get_source(config, 'source_two').source == str(
        (tmp_path / 'home/sample/rules').resolve()
    )
    flow = get_flow(config, 'financedata')
    assert flow.input == str((tmp_path / 'data-raw/finance.csv.gz').resolve())
    assert flow.output == str((tmp_path / 'data/finance.csv').resolve())
    assert get_source(config, 'source_one').source.startswith('https://')


def test_rejects_trailing_comma(tmp_path: Path):
    (tmp_path / 'zendt.json').write_text(
        '{"sources": [], "flows": [],}',
        encoding='utf-8',
    )
    with pytest.raises(ConfigError, match='Invalid JSON'):
        load_config(tmp_path / 'zendt.json')


def test_source_id_cannot_contain_slash(tmp_path: Path):
    data = {
        'sources': [{'id': 'foo/bar', 'source': '/tmp/rules'}],
        'flows': [],
    }
    with pytest.raises(ConfigError, match="cannot contain '/'"):
        load_config(write_config(tmp_path, data))


def test_duplicate_source_ids(tmp_path: Path):
    data = {
        'sources': [
            {'id': 'a', 'source': '/tmp/one'},
            {'id': 'a', 'source': '/tmp/two'},
        ],
        'flows': [],
    }
    with pytest.raises(ConfigError, match='Source ids'):
        load_config(write_config(tmp_path, data))


def test_duplicate_flow_ids(tmp_path: Path):
    data = {
        'sources': [{'id': 's', 'source': '/tmp/rules'}],
        'flows': [
            {'id': 'f', 'rules': ['r1']},
            {'id': 'f', 'rules': ['r2']},
        ],
    }
    with pytest.raises(ConfigError, match='Flow ids'):
        load_config(write_config(tmp_path, data))


def test_unknown_flow_id(tmp_path: Path):
    config = load_config(write_config(tmp_path, SAMPLE))
    with pytest.raises(ConfigError, match='not found'):
        get_flow(config, 'does_not_exist')


def test_missing_required_source_key(tmp_path: Path):
    data = {'sources': [{'id': 's'}], 'flows': []}
    with pytest.raises(ConfigError, match='missing required'):
        load_config(write_config(tmp_path, data))


def test_unknown_parameter_is_ignored(tmp_path: Path):
    data = {
        'sources': [{'id': 's', 'source': '/tmp', 'selection': ['x']}],
        'flows': [],
    }
    config = load_config(write_config(tmp_path, data))
    assert get_source(config, 's').source == '/tmp'


def test_yaml_file_reads_sources(tmp_path: Path):
    path = tmp_path / 'datapackage.yaml'
    path.write_text(
        'name: other\n'
        'sources:\n'
        '  - id: relatorios\n'
        '    source: https://github.com/user/repo\n'
        'flows: []\n',
        encoding='utf-8',
    )
    config = load_config(path)
    assert [source.id for source in config.sources] == ['relatorios']


def test_yaml_nested_zendt_config_list(tmp_path: Path):
    path = tmp_path / 'datapackage.yaml'
    path.write_text(
        'name: pkg\n'
        'zendt_config:\n'
        '  - sources:\n'
        '    - id: relatorios\n'
        '      source: https://github.com/user/repo\n'
        '  - flows:\n'
        '    - id: receita\n'
        '      rules: [is_asps_rec]\n',
        encoding='utf-8',
    )
    config = load_config(path)
    assert get_source(config, 'relatorios').source.startswith('https://')
    assert get_flow(config, 'receita').rules == ['is_asps_rec']


def test_load_default_config_prefers_zendt_json(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'zendt.json').write_text(
        json.dumps({
            'sources': [{'id': 'from_file', 'source': 'https://a.example'}],
            'flows': [],
        }),
        encoding='utf-8',
    )
    monkeypatch.setenv(
        'sources',
        json.dumps([{'id': 'from_env', 'source': 'https://b.example'}]),
    )
    monkeypatch.setenv('config', 'other.yaml')
    config = load_default_config()
    assert [source.id for source in config.sources] == ['from_file']


def test_load_default_config_uses_config_env(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('sources', raising=False)
    monkeypatch.delenv('flows', raising=False)
    path = tmp_path / 'pkg.yaml'
    path.write_text(
        'sources:\n  - id: from_config\n    source: https://c.example\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('config', 'pkg.yaml')
    monkeypatch.setenv(
        'sources',
        json.dumps([{'id': 'from_env', 'source': 'https://b.example'}]),
    )
    config = load_default_config()
    assert [source.id for source in config.sources] == ['from_config']


def test_load_default_config_uses_zendt_json(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('config', raising=False)
    monkeypatch.delenv('sources', raising=False)
    monkeypatch.delenv('flows', raising=False)
    write_config(tmp_path, SAMPLE)
    config = load_default_config()
    assert [source.id for source in config.sources] == [
        'source_one',
        'source_two',
    ]


def test_load_default_config_missing(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('config', raising=False)
    monkeypatch.delenv('CONFIG', raising=False)
    monkeypatch.delenv('sources', raising=False)
    monkeypatch.delenv('SOURCES', raising=False)
    monkeypatch.delenv('flows', raising=False)
    monkeypatch.delenv('FLOWS', raising=False)
    with pytest.raises(ConfigError, match='No source configuration'):
        load_default_config()


def test_file_without_sources(tmp_path: Path):
    path = tmp_path / 'other.yaml'
    path.write_text('name: pkg\nresources: []\n', encoding='utf-8')
    with pytest.raises(ConfigError, match='sources are missing'):
        load_config(path)


def test_find_config_missing_returns_none(tmp_path: Path):
    assert find_config(tmp_path) is None


def test_load_config_missing_file(tmp_path: Path):
    with pytest.raises(ConfigError, match='not found'):
        load_config(tmp_path / 'zendt.json')


def test_source_id_slash_and_empty_sources(tmp_path: Path):
    slash = tmp_path / 'slash.json'
    slash.write_text(
        json.dumps({
            'sources': [
                {'id': 'a/b', 'source': 'https://github.com/user/repo'}
            ]
        }),
        encoding='utf-8',
    )
    with pytest.raises(ConfigError, match='cannot contain'):
        load_config(slash)

    empty = tmp_path / 'empty.json'
    empty.write_text(json.dumps({'sources': []}), encoding='utf-8')
    with pytest.raises(ConfigError, match='no sources'):
        load_config(empty)


def test_sources_env_merges_flows_env(tmp_path: Path, monkeypatch):
    from zendt.rules.configs import load_config_from_env

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('config', raising=False)
    monkeypatch.delenv('CONFIG', raising=False)
    monkeypatch.setenv(
        'sources',
        json.dumps([
            {'id': 'env_src', 'source': 'https://github.com/user/repo'}
        ]),
    )
    monkeypatch.setenv(
        'flows', json.dumps([{'id': 'score', 'rules': ['flag']}])
    )
    config = load_config_from_env()
    assert config is not None
    assert get_flow(config, 'score').rules == ['flag']


def test_sources_env_accepts_one_source_object(tmp_path: Path, monkeypatch):
    from zendt.rules.configs import load_config_from_env

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('config', raising=False)
    monkeypatch.delenv('CONFIG', raising=False)
    monkeypatch.delenv('flows', raising=False)
    monkeypatch.delenv('FLOWS', raising=False)
    monkeypatch.setenv(
        'sources',
        json.dumps({'id': 'only', 'source': 'https://github.com/user/repo'}),
    )
    config = load_config_from_env()
    assert config is not None
    assert [source.id for source in config.sources] == ['only']
    assert config.flows == []


def test_sources_env_rejects_embedded_flows(tmp_path: Path, monkeypatch):
    from zendt.rules.configs import load_config_from_env

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('config', raising=False)
    monkeypatch.delenv('CONFIG', raising=False)
    monkeypatch.setenv(
        'sources',
        json.dumps({
            'sources': [
                {'id': 'env_src', 'source': 'https://github.com/user/repo'}
            ],
            'flows': [{'id': 'score', 'rules': ['flag']}],
        }),
    )
    monkeypatch.setenv(
        'flows', json.dumps([{'id': 'other', 'rules': ['flag']}])
    )
    with pytest.raises(ConfigError, match='without flows'):
        load_config_from_env()


def test_uppercase_config_env_and_invalid_files(tmp_path: Path, monkeypatch):
    from zendt.rules.configs import load_config_from_env

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('config', raising=False)
    path = tmp_path / 'pkg.yaml'
    path.write_text(
        'sources:\n  - id: from_upper\n    source: https://d.example\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('CONFIG', 'pkg.yaml')
    assert [source.id for source in load_config_from_env().sources] == [
        'from_upper'
    ]

    bad_type = tmp_path / 'notes.txt'
    bad_type.write_text('sources: []', encoding='utf-8')
    with pytest.raises(ConfigError, match='Unsupported'):
        load_config(bad_type)

    bad_yaml = tmp_path / 'broken.yaml'
    bad_yaml.write_text('sources: [\n', encoding='utf-8')
    with pytest.raises(ConfigError, match='Invalid YAML'):
        load_config(bad_yaml)

    empty_rules = tmp_path / 'empty-rules.json'
    empty_rules.write_text(
        json.dumps({
            'sources': [{'id': 's', 'source': 'https://e.example'}],
            'flows': [{'id': 'f', 'rules': []}],
        }),
        encoding='utf-8',
    )
    with pytest.raises(ConfigError, match='non-empty'):
        load_config(empty_rules)


def test_sources_env_rejects_invalid_json(monkeypatch):
    from zendt.rules.configs import load_config_from_env

    monkeypatch.delenv('config', raising=False)
    monkeypatch.delenv('CONFIG', raising=False)
    monkeypatch.setenv('sources', '{')
    with pytest.raises(ConfigError, match='Invalid JSON'):
        load_config_from_env()
