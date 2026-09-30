import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from zendt.errors import AmbiguousRule, AuthError, RuleNotFound, SourceError
from zendt.models import ResolvedSource
from zendt.rules.catalog import build_catalog, catalog_rules, resolve_rule

MIN_JDM = {
    'nodes': [{'id': 'in', 'type': 'inputNode', 'name': 'Request'}],
    'edges': [],
}


def write_jdm(path: Path, name: str = 'flag_rule') -> Path:
    file = path / f'{name}.json'
    file.write_text(json.dumps(MIN_JDM), encoding='utf-8')
    return file


def test_catalog_rules_local_dir(tmp_path: Path):
    write_jdm(tmp_path, 'is_asps_desp')
    write_jdm(tmp_path, 'is_mde_desp')
    (tmp_path / 'zendt.json').write_text('{}', encoding='utf-8')
    (tmp_path / 'notes.txt').write_text('nope', encoding='utf-8')

    rules = catalog_rules(str(tmp_path))
    assert set(rules) == {'is_asps_desp', 'is_mde_desp'}
    assert rules['is_asps_desp'].origin.endswith('is_asps_desp.json')
    assert rules['is_asps_desp'].key == 'is_asps_desp'
    assert rules['is_mde_desp'].key == 'is_mde_desp'


def test_catalog_rules_local_single_file(tmp_path: Path):
    file = write_jdm(tmp_path, 'one_rule')
    rules = catalog_rules(str(file))
    assert set(rules) == {'one_rule'}
    assert rules['one_rule'].origin == str(file)
    assert rules['one_rule'].key == 'one_rule'


def test_catalog_rules_local_does_not_read_json_bodies(tmp_path: Path):
    write_jdm(tmp_path, 'ok_rule')
    (tmp_path / 'broken.json').write_text('{not json', encoding='utf-8')

    rules = catalog_rules(str(tmp_path))
    assert set(rules) == {'ok_rule', 'broken'}


def test_catalog_rules_local_rejects_version(tmp_path: Path):
    write_jdm(tmp_path)
    with pytest.raises(SourceError, match='--version'):
        catalog_rules(str(tmp_path), version='v1')


def test_catalog_rules_github_folder_uses_trees_api():
    listing = Mock(status_code=200, ok=True)
    listing.json.return_value = {
        'truncated': False,
        'tree': [
            {'type': 'blob', 'path': 'is_asps_desp.json'},
            {'type': 'blob', 'path': 'readme.md'},
            {'type': 'tree', 'path': 'subdir'},
            {'type': 'blob', 'path': 'nested/is_mde_desp.json'},
        ],
    }
    with patch(
        'zendt.rules.catalog.requests.get', return_value=listing
    ) as get:
        rules = catalog_rules('https://github.com/user/repo')

    assert get.call_count == 1
    assert '/git/trees/HEAD' in get.call_args.args[0]
    assert get.call_args.kwargs['params'] == {'recursive': '1'}
    assert rules['is_asps_desp'].origin == (
        'https://raw.githubusercontent.com/user/repo/HEAD/is_asps_desp.json'
    )
    assert rules['is_asps_desp'].key == 'is_asps_desp'
    assert rules['is_mde_desp'].origin == (
        'https://raw.githubusercontent.com/user/repo/HEAD/nested/is_mde_desp.json'
    )
    assert rules['is_mde_desp'].key == 'nested/is_mde_desp'


def test_catalog_rules_github_folder_prefix():
    listing = Mock(status_code=200, ok=True)
    listing.json.return_value = {
        'tree': [
            {'type': 'blob', 'path': 'rules/keep.json'},
            {'type': 'blob', 'path': 'other/skip.json'},
        ]
    }
    with patch('zendt.rules.catalog.requests.get', return_value=listing):
        rules = catalog_rules('https://github.com/user/repo/tree/main/rules')
    assert set(rules) == {'keep'}
    assert rules['keep'].origin.endswith('main/rules/keep.json')
    assert rules['keep'].key == 'keep'


def test_catalog_rules_remote_single_json():
    with patch('zendt.rules.catalog.requests.get') as get:
        rules = catalog_rules(
            'https://github.com/user/repo/blob/main/rules/flag_rule.json'
        )
    get.assert_not_called()
    assert set(rules) == {'flag_rule'}
    assert rules['flag_rule'].origin == (
        'https://raw.githubusercontent.com/user/repo/main/rules/flag_rule.json'
    )
    assert rules['flag_rule'].key == 'flag_rule'


def test_catalog_rules_github_ssh_url_uses_trees_api():
    listing = Mock(status_code=200, ok=True)
    listing.json.return_value = {
        'truncated': False,
        'tree': [{'type': 'blob', 'path': 'is_asps_desp.json'}],
    }
    with patch(
        'zendt.rules.catalog.requests.get', return_value=listing
    ) as get:
        rules = catalog_rules('git@github.com:user/repo.git', version='main')

    assert '/repos/user/repo/git/trees/main' in get.call_args.args[0]
    assert rules['is_asps_desp'].origin == (
        'https://raw.githubusercontent.com/user/repo/main/is_asps_desp.json'
    )


def test_catalog_rules_rejects_gitlab():
    with pytest.raises(SourceError, match='GitHub'):
        catalog_rules('https://gitlab.com/user/rules_repo')
    with pytest.raises(SourceError, match='GitHub'):
        catalog_rules('git@gitlab.com:user/rules_repo.git')


def test_catalog_rules_github_version_overrides_the_url_ref():
    listing = Mock(status_code=200, ok=True)
    listing.json.return_value = {
        'tree': [{'type': 'blob', 'path': 'rules/keep.json'}]
    }
    with patch(
        'zendt.rules.catalog.requests.get', return_value=listing
    ) as get:
        rules = catalog_rules(
            'https://github.com/user/repo/tree/main/rules', version='v9'
        )
    assert '/git/trees/v9' in get.call_args.args[0]
    assert rules['keep'].origin.endswith('v9/rules/keep.json')


def test_catalog_rules_sends_the_bearer_token():
    listing = Mock(status_code=200, ok=True)
    listing.json.return_value = {'tree': []}
    with patch(
        'zendt.rules.catalog.requests.get', return_value=listing
    ) as get:
        catalog_rules('https://github.com/user/repo', token='secret')
    assert get.call_args.kwargs['headers']['Authorization'] == 'Bearer secret'


def test_catalog_rules_github_unauthorized():
    listing = Mock(status_code=401, ok=False)
    with patch('zendt.rules.catalog.requests.get', return_value=listing):
        with pytest.raises(AuthError):
            catalog_rules('https://github.com/user/repo')


def test_catalog_rules_github_http_error():
    listing = Mock(status_code=500, ok=False)
    with patch('zendt.rules.catalog.requests.get', return_value=listing):
        with pytest.raises(SourceError, match='HTTP 500'):
            catalog_rules('https://github.com/user/repo')


def test_catalog_rules_github_request_failure():
    with patch(
        'zendt.rules.catalog.requests.get',
        side_effect=requests.RequestException('offline'),
    ):
        with pytest.raises(SourceError, match='Could not fetch'):
            catalog_rules('https://github.com/user/repo')


def test_catalog_rules_rejects_a_truncated_tree():
    listing = Mock(status_code=200, ok=True)
    listing.json.return_value = {'truncated': True, 'tree': []}
    with patch('zendt.rules.catalog.requests.get', return_value=listing):
        with pytest.raises(SourceError, match='too large'):
            catalog_rules('https://github.com/user/repo')


def test_catalog_rules_local_file_must_be_json(tmp_path: Path):
    path = tmp_path / 'rules.txt'
    path.write_text('amount\n1\n', encoding='utf-8')
    with pytest.raises(SourceError, match='not JSON'):
        catalog_rules(str(path))


def test_catalog_rules_local_nested_key(tmp_path: Path):
    nested = tmp_path / 'transf_uniao'
    nested.mkdir()
    write_jdm(nested, 'is_fpe_principal')
    write_jdm(tmp_path, 'is_impostos')

    rules = catalog_rules(str(tmp_path))
    assert rules['is_fpe_principal'].key == 'transf_uniao/is_fpe_principal'
    assert rules['is_impostos'].key == 'is_impostos'


def test_same_stem_inside_one_source_is_an_error(tmp_path: Path):
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    write_jdm(tmp_path / 'a', 'student_discount')
    write_jdm(tmp_path / 'b', 'student_discount')
    with pytest.raises(
        SourceError, match="Duplicate rule name 'student_discount'"
    ):
        catalog_rules(str(tmp_path))


def test_build_catalog_keeps_same_name_from_two_sources(tmp_path: Path):
    one = tmp_path / 'one'
    two = tmp_path / 'two'
    one.mkdir()
    two.mkdir()
    write_jdm(one, 'student_discount')
    write_jdm(two, 'student_discount')
    write_jdm(two, 'age_discount')

    catalog = build_catalog([
        ResolvedSource(source=str(one), id='source_one'),
        ResolvedSource(source=str(two), id='source_two'),
    ])
    assert [entry.ref for entry in catalog] == [
        'source_one/student_discount',
        'source_two/age_discount',
        'source_two/student_discount',
    ]

    assert resolve_rule(catalog, 'age_discount').origin.endswith(
        'age_discount.json'
    )
    assert resolve_rule(catalog, 'age_discount').key == 'age_discount'
    discount_one = resolve_rule(catalog, 'source_one/student_discount')
    discount_two = resolve_rule(catalog, 'source_two/student_discount')
    assert discount_one.source_id == 'source_one'
    assert discount_one.key == 'student_discount'
    assert discount_two.key == 'student_discount'
    with pytest.raises(AmbiguousRule, match='source_one and source_two'):
        resolve_rule(catalog, 'student_discount')
    with pytest.raises(RuleNotFound, match='source_two/missing'):
        resolve_rule(catalog, 'source_two/missing')
