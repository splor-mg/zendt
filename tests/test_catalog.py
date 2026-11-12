import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from zendt.errors import (
    AmbiguousRule,
    AuthError,
    RateLimitError,
    RuleNotFound,
    SourceError,
    SourceUnavailable,
)
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


def test_catalog_rules_skips_metadata_files(tmp_path: Path):
    write_jdm(tmp_path, 'is_asps_desp')
    write_jdm(tmp_path, 'customer_meta')
    for name in (
        'zendt.json',
        'meta.json',
        '_meta.json',
        'metadata.json',
        '_metadata.json',
    ):
        (tmp_path / name).write_text('{}', encoding='utf-8')
    nested = tmp_path / 'DCAF'
    nested.mkdir()
    write_jdm(nested, 'keep')
    (nested / '_meta.json').write_text('{}', encoding='utf-8')

    rules = catalog_rules(str(tmp_path))
    assert set(rules) == {'is_asps_desp', 'customer_meta', 'keep'}


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


COMMIT_SHA = 'commit-sha'
ROOT_TREE_SHA = 'root-tree-sha'


def github_response(status: int, payload, *, ok: bool = True) -> Mock:
    listing = Mock(status_code=status, ok=ok)
    listing.json.return_value = payload
    return listing


def commit_response() -> Mock:
    return github_response(
        200,
        {
            'sha': COMMIT_SHA,
            'commit': {'tree': {'sha': ROOT_TREE_SHA}},
        },
    )


def test_catalog_rules_github_root_uses_contents_api():
    root = github_response(
        200,
        [
            {'type': 'file', 'path': 'is_asps_desp.json'},
            {'type': 'file', 'path': 'readme.md'},
            {'type': 'file', 'path': 'zendt.json'},
            {'type': 'file', 'path': 'meta.json'},
            {'type': 'file', 'path': '_meta.json'},
            {'type': 'file', 'path': 'metadata.json'},
            {'type': 'file', 'path': '_metadata.json'},
            {'type': 'dir', 'path': 'nested', 'sha': 'nested-sha'},
        ],
    )
    nested = github_response(
        200,
        [
            {'type': 'file', 'path': 'nested/is_mde_desp.json'},
            {'type': 'file', 'path': 'nested/_meta.json'},
        ],
    )
    with patch(
        'zendt.rules.catalog.requests.get',
        side_effect=[commit_response(), root, nested],
    ) as get:
        rules = catalog_rules('https://github.com/user/repo')

    assert [call.args[0] for call in get.call_args_list] == [
        'https://api.github.com/repos/user/repo/commits/HEAD',
        'https://api.github.com/repos/user/repo/contents',
        'https://api.github.com/repos/user/repo/contents/nested',
    ]
    assert get.call_args_list[1].kwargs['params'] == {'ref': COMMIT_SHA}
    assert get.call_args_list[2].kwargs['params'] == {'ref': COMMIT_SHA}
    assert set(rules) == {'is_asps_desp', 'is_mde_desp'}
    assert rules['is_asps_desp'].origin == (
        'https://raw.githubusercontent.com/user/repo/'
        f'{COMMIT_SHA}/is_asps_desp.json'
    )
    assert rules['is_asps_desp'].key == 'is_asps_desp'
    assert rules['is_mde_desp'].origin == (
        'https://raw.githubusercontent.com/user/repo/'
        f'{COMMIT_SHA}/nested/is_mde_desp.json'
    )
    assert rules['is_mde_desp'].key == 'nested/is_mde_desp'


def test_catalog_rules_github_folder_uses_contents_and_ref():
    folder = github_response(
        200,
        [
            {'type': 'file', 'path': 'rules/keep.json'},
            {'type': 'dir', 'path': 'rules/nested'},
        ],
    )
    nested = github_response(
        200,
        [{'type': 'file', 'path': 'rules/nested/other.json'}],
    )
    with patch(
        'zendt.rules.catalog.requests.get',
        side_effect=[commit_response(), folder, nested],
    ) as get:
        rules = catalog_rules('https://github.com/user/repo/tree/main/rules')

    assert set(rules) == {'keep', 'other'}
    assert rules['keep'].origin.endswith(f'{COMMIT_SHA}/rules/keep.json')
    assert rules['keep'].key == 'keep'
    assert rules['other'].key == 'nested/other'
    assert rules['other'].origin.endswith(
        f'{COMMIT_SHA}/rules/nested/other.json'
    )
    assert [call.args[0] for call in get.call_args_list] == [
        'https://api.github.com/repos/user/repo/commits/main',
        'https://api.github.com/repos/user/repo/contents/rules',
        'https://api.github.com/repos/user/repo/contents/rules/nested',
    ]
    assert get.call_args_list[1].kwargs['params'] == {'ref': COMMIT_SHA}
    assert get.call_args_list[2].kwargs['params'] == {'ref': COMMIT_SHA}


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


def test_catalog_rules_github_ssh_url_uses_contents_api():
    listing = github_response(
        200,
        [{'type': 'file', 'path': 'is_asps_desp.json'}],
    )
    with patch(
        'zendt.rules.catalog.requests.get',
        side_effect=[commit_response(), listing],
    ) as get:
        rules = catalog_rules('git@github.com:user/repo.git', version='main')

    assert [call.args[0] for call in get.call_args_list] == [
        'https://api.github.com/repos/user/repo/commits/main',
        'https://api.github.com/repos/user/repo/contents',
    ]
    assert get.call_args.kwargs['params'] == {'ref': COMMIT_SHA}
    assert rules['is_asps_desp'].origin == (
        'https://raw.githubusercontent.com/user/repo/'
        f'{COMMIT_SHA}/is_asps_desp.json'
    )


def test_catalog_rules_rejects_gitlab():
    with pytest.raises(SourceError, match='GitHub'):
        catalog_rules('https://gitlab.com/user/rules_repo')
    with pytest.raises(SourceError, match='GitHub'):
        catalog_rules('git@gitlab.com:user/rules_repo.git')


def test_catalog_rules_github_version_overrides_the_url_ref():
    listing = github_response(
        200,
        [{'type': 'file', 'path': 'rules/keep.json'}],
    )
    with patch(
        'zendt.rules.catalog.requests.get',
        side_effect=[commit_response(), listing],
    ) as get:
        rules = catalog_rules(
            'https://github.com/user/repo/tree/main/rules', version='v9'
        )
    assert [call.args[0] for call in get.call_args_list] == [
        'https://api.github.com/repos/user/repo/commits/v9',
        'https://api.github.com/repos/user/repo/contents/rules',
    ]
    assert get.call_args.kwargs['params'] == {'ref': COMMIT_SHA}
    assert rules['keep'].origin.endswith(f'{COMMIT_SHA}/rules/keep.json')


def test_catalog_rules_sends_the_bearer_token():
    listing = github_response(200, [])
    with patch(
        'zendt.rules.catalog.requests.get',
        side_effect=[commit_response(), listing],
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


def test_catalog_rules_folder_too_large_uses_that_directory_tree():
    contents = github_response(
        403,
        {
            'message': (
                'Sorry, this directory is too large for the Contents API. '
                'Use the Git Trees API instead.'
            )
        },
        ok=False,
    )
    root = github_response(
        200,
        {
            'tree': [
                {'type': 'tree', 'path': 'rules', 'sha': 'rules-sha'},
            ]
        },
    )
    dcaf = github_response(
        200,
        {
            'tree': [
                {'type': 'tree', 'path': 'DCAF', 'sha': 'dcaf-sha'},
            ]
        },
    )
    relatorios = github_response(
        200,
        {
            'tree': [
                {
                    'type': 'tree',
                    'path': 'relatorios',
                    'sha': 'relatorios-sha',
                },
            ]
        },
    )
    folder = github_response(
        200,
        {
            'truncated': False,
            'tree': [
                {'type': 'blob', 'path': 'keep.json'},
                {'type': 'blob', 'path': 'nested/other.json'},
                {'type': 'blob', 'path': 'notes.md'},
            ],
        },
    )
    with patch(
        'zendt.rules.catalog.requests.get',
        side_effect=[
            commit_response(),
            contents,
            root,
            dcaf,
            relatorios,
            folder,
        ],
    ) as get:
        rules = catalog_rules(
            'https://github.com/user/repo/tree/main/rules/DCAF/relatorios'
        )

    assert set(rules) == {'keep', 'other'}
    assert rules['keep'].key == 'keep'
    assert rules['other'].key == 'nested/other'
    assert rules['keep'].origin.endswith(
        f'{COMMIT_SHA}/rules/DCAF/relatorios/keep.json'
    )
    assert rules['other'].origin.endswith(
        f'{COMMIT_SHA}/rules/DCAF/relatorios/nested/other.json'
    )
    assert [call.args[0] for call in get.call_args_list] == [
        'https://api.github.com/repos/user/repo/commits/main',
        'https://api.github.com/repos/user/repo/contents/rules/DCAF/relatorios',
        f'https://api.github.com/repos/user/repo/git/trees/{ROOT_TREE_SHA}',
        'https://api.github.com/repos/user/repo/git/trees/rules-sha',
        'https://api.github.com/repos/user/repo/git/trees/dcaf-sha',
        'https://api.github.com/repos/user/repo/git/trees/relatorios-sha',
    ]
    assert get.call_args_list[1].kwargs['params'] == {'ref': COMMIT_SHA}
    assert get.call_args_list[2].kwargs['params'] is None
    assert get.call_args.kwargs['params'] == {'recursive': '1'}


def test_catalog_rules_truncated_tree_aborts():
    contents = github_response(
        403,
        {'message': 'This directory is too large. Use the Trees API.'},
        ok=False,
    )
    root = github_response(
        200,
        {'tree': [{'type': 'tree', 'path': 'rules', 'sha': 'rules-sha'}]},
    )
    truncated = github_response(
        200,
        {
            'truncated': True,
            'tree': [{'type': 'blob', 'path': 'missing.json'}],
        },
    )
    with (
        patch(
            'zendt.rules.catalog.requests.get',
            side_effect=[commit_response(), contents, root, truncated],
        ) as get,
        pytest.raises(SourceError, match='exceeds GitHub API limits'),
    ):
        catalog_rules('https://github.com/user/repo/tree/v9/rules')

    assert get.call_args.kwargs['params'] == {'recursive': '1'}
    assert get.call_args.args[0].endswith('/git/trees/rules-sha')


def test_catalog_rules_gateway_error_does_not_fall_back_to_trees():
    contents = github_response(
        504,
        {'message': 'Server Error'},
        ok=False,
    )
    with (
        patch(
            'zendt.rules.catalog.requests.get',
            side_effect=[commit_response(), contents],
        ) as get,
        pytest.raises(SourceUnavailable, match='HTTP 504'),
    ):
        catalog_rules('https://github.com/user/repo')

    assert [call.args[0] for call in get.call_args_list] == [
        'https://api.github.com/repos/user/repo/commits/HEAD',
        'https://api.github.com/repos/user/repo/contents',
    ]


def test_catalog_rules_contents_timeout_does_not_fall_back_to_trees():
    with (
        patch(
            'zendt.rules.catalog.requests.get',
            side_effect=[commit_response(), requests.Timeout('timed out')],
        ) as get,
        pytest.raises(SourceUnavailable, match='temporarily unavailable'),
    ):
        catalog_rules('https://github.com/user/repo/tree/v1.2.1/rules')

    assert [call.args[0] for call in get.call_args_list] == [
        'https://api.github.com/repos/user/repo/commits/v1.2.1',
        'https://api.github.com/repos/user/repo/contents/rules',
    ]


def test_catalog_rules_rate_limit_is_not_an_auth_error():
    limited = github_response(
        403,
        {'message': 'API rate limit exceeded for 1.2.3.4.'},
        ok=False,
    )
    with (
        patch(
            'zendt.rules.catalog.requests.get',
            side_effect=[commit_response(), limited],
        ),
        pytest.raises(RateLimitError, match='rate limit exceeded'),
    ):
        catalog_rules('https://github.com/user/repo/tree/main/rules')


def test_catalog_rules_github_forbidden_without_size_message():
    listing = github_response(
        403,
        {'message': 'Resource not accessible by integration'},
        ok=False,
    )
    with patch('zendt.rules.catalog.requests.get', return_value=listing):
        with pytest.raises(AuthError):
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
