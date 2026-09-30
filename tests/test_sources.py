from unittest.mock import Mock, patch

import pytest

from zendt.errors import AuthError, ConfigError, SourceError
from zendt.rules.sources import (
    find_local,
    find_remote,
    parse_github,
    resolve_sources,
)
from zendt.utils.paths import is_remote, resolve_path


def test_is_remote():
    assert is_remote('https://github.com/user/repo')
    assert is_remote('git@github.com:user/repo.git')
    assert is_remote('ssh://git@github.com/user/repo.git')
    assert not is_remote('home/sample/rules')


def test_resolve_path_keeps_url():
    url = 'https://github.com/user/repo'
    assert resolve_path(url) == url


def test_resolve_path_relative_to_base(tmp_path):
    assert resolve_path('rules', tmp_path) == str(
        (tmp_path / 'rules').resolve()
    )


def test_parse_github_folder_and_blob():
    folder = parse_github('https://github.com/user/repo/tree/main/rules')
    assert folder == {
        'host': 'github',
        'owner': 'user',
        'repo': 'repo',
        'ref': 'main',
        'path': 'rules',
    }
    blob = parse_github(
        'https://github.com/user/repo/blob/v1.2.1/rules/flag_rule.json'
    )
    assert blob['path'] == 'rules/flag_rule.json'
    assert blob['ref'] == 'v1.2.1'


def test_parse_github_raw_url_and_git_suffix():
    raw = parse_github(
        'https://raw.githubusercontent.com/user/repo/v1/rules/flag.json'
    )
    assert raw == {
        'host': 'github',
        'owner': 'user',
        'repo': 'repo',
        'ref': 'v1',
        'path': 'rules/flag.json',
    }
    repo = parse_github('https://github.com/user/repo.git')
    assert repo['repo'] == 'repo'
    assert repo['path'] == ''


def test_parse_github_ssh_urls():
    scp = parse_github('git@github.com:user/repo.git')
    assert scp == {
        'host': 'github',
        'owner': 'user',
        'repo': 'repo',
        'ref': None,
        'path': '',
    }
    ssh = parse_github('ssh://git@github.com/user/repo.git')
    assert ssh['owner'] == 'user'
    assert ssh['repo'] == 'repo'
    assert ssh['ref'] is None
    assert ssh['path'] == ''


def test_parse_github_rejects_other_hosts():
    assert parse_github('https://gitlab.com/user/rules_repo') is None
    assert parse_github('git@gitlab.com:user/rules_repo.git') is None
    assert parse_github('ssh://git@gitlab.com/user/rules_repo.git') is None


def test_find_local_file_and_dir(tmp_path):
    file = tmp_path / 'flag_rule.json'
    file.write_text('{}', encoding='utf-8')
    assert find_local(str(file)) == str(file)
    assert find_local(str(tmp_path)) == str(tmp_path)


def test_find_local_missing(tmp_path):
    with pytest.raises(SourceError, match='not found'):
        find_local(str(tmp_path / 'missing'))


def test_find_remote_ok():
    response = Mock(status_code=200, ok=True)
    with patch(
        'zendt.rules.sources.requests.get', return_value=response
    ) as get:
        assert (
            find_remote('https://github.com/user/repo')
            == 'https://github.com/user/repo'
        )
        get.assert_called_once()
        assert 'token=' not in get.call_args.args[0]


def test_find_remote_sends_bearer_token():
    response = Mock(status_code=200, ok=True)
    with patch(
        'zendt.rules.sources.requests.get', return_value=response
    ) as get:
        find_remote('https://github.com/user/repo', auth='secret-token')
        headers = get.call_args.kwargs['headers']
        assert headers['Authorization'] == 'Bearer secret-token'


def test_find_remote_unauthorized():
    response = Mock(status_code=401, ok=False)
    with patch('zendt.rules.sources.requests.get', return_value=response):
        with pytest.raises(AuthError):
            find_remote('https://github.com/user/repo', auth='bad')


def test_find_remote_network_error():
    with patch(
        'zendt.rules.sources.requests.get',
        side_effect=__import__('requests').RequestException('offline'),
    ):
        with pytest.raises(SourceError, match='Could not reach'):
            find_remote('https://github.com/user/repo')


def test_find_remote_not_found():
    response = Mock(status_code=404, ok=False)
    with patch('zendt.rules.sources.requests.get', return_value=response):
        with pytest.raises(SourceError, match='not accessible'):
            find_remote('https://github.com/user/repo')


def test_resolve_sources_omitted_uses_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('sources', raising=False)
    monkeypatch.delenv('source', raising=False)
    monkeypatch.delenv('flows', raising=False)
    (tmp_path / 'zendt.json').write_text(
        '{"sources": [{"id": "rules", '
        '"source": "https://github.com/user/repo"}], "flows": []}',
        encoding='utf-8',
    )
    resolved = resolve_sources(None)
    assert len(resolved) == 1
    assert resolved[0].id == 'rules'
    assert resolved[0].source == 'https://github.com/user/repo'


def test_resolve_sources_by_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'zendt.json').write_text(
        '{"sources": [{"id": "rules", "source": "./jdm"}], "flows": []}',
        encoding='utf-8',
    )
    resolved = resolve_sources('rules')
    assert len(resolved) == 1
    assert resolved[0].id == 'rules'
    assert resolved[0].source == str((tmp_path / 'jdm').resolve())


def test_resolve_sources_unknown_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'zendt.json').write_text(
        '{"sources": [{"id": "rules", "source": "./jdm"}], "flows": []}',
        encoding='utf-8',
    )
    with pytest.raises(ConfigError, match='not found'):
        resolve_sources('missing')


def test_resolve_sources_local_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rules_dir = tmp_path / 'other-rules'
    rules_dir.mkdir()
    resolved = resolve_sources(str(rules_dir))
    assert resolved[0].source == str(rules_dir)
    assert resolved[0].id is None


def test_resolve_sources_yaml_path_is_a_file_not_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / 'pkg.yaml'
    path.write_text(
        'sources:\n  - id: relatorios\n    source: https://github.com/user/repo\n',
        encoding='utf-8',
    )
    resolved = resolve_sources(str(path))
    assert len(resolved) == 1
    assert resolved[0].id is None
    assert resolved[0].source == str(path.resolve())


def test_resolve_sources_omitted_uses_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('config', raising=False)
    monkeypatch.delenv('CONFIG', raising=False)
    monkeypatch.setenv(
        'sources',
        '[{"id": "env_src", "source": "https://github.com/user/repo"}]',
    )
    resolved = resolve_sources(None)
    assert resolved[0].id == 'env_src'


def test_resolve_sources_github_url():
    resolved = resolve_sources('https://github.com/user/repo')
    assert resolved[0].source == 'https://github.com/user/repo'
    assert resolved[0].id is None


def test_resolve_sources_reads_the_named_token(monkeypatch):
    monkeypatch.setenv('GH_TOKEN', 'secret')
    resolved = resolve_sources(
        'https://github.com/user/repo',
        auth_var='GH_TOKEN',
        version_arg='1.2.1',
    )
    assert resolved[0].token == 'secret'
    assert resolved[0].version == '1.2.1'


def test_resolve_sources_missing_token_name_is_empty(monkeypatch):
    monkeypatch.delenv('MISSING', raising=False)
    resolved = resolve_sources(
        'https://github.com/user/repo', auth_var='MISSING'
    )
    assert resolved[0].token is None
