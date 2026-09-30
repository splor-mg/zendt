import json
from pathlib import Path

import pytest

from zendt.engine.load import load_queued_rules, resolve_entries
from zendt.errors import RuleInvalidError, RuleNotFound
from zendt.models import ResolvedSource
from zendt.rules.catalog import build_catalog


def write_graph(
    path: Path, name: str, children: list[str] | None = None
) -> None:
    nodes = [{'id': 'in', 'type': 'inputNode', 'name': 'Request'}]
    for key in children or []:
        nodes.append({
            'type': 'decisionNode',
            'id': key,
            'name': key,
            'content': {'key': key},
        })
    file = path / f'{name}.json'
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        json.dumps({'nodes': nodes, 'edges': []}), encoding='utf-8'
    )


def test_load_content_returns_the_graph(tmp_path: Path):
    write_graph(tmp_path, 'is_asps_rec', ['is_impostos'])
    catalog = build_catalog([
        ResolvedSource(source=str(tmp_path), id='regras')
    ])
    entry = resolve_entries(catalog, ['is_asps_rec'])[0]

    body = entry.load_content()

    assert body['nodes'][1]['content']['key'] == 'is_impostos'


def test_load_content_rejects_a_non_jdm_object(tmp_path: Path):
    (tmp_path / 'notes.json').write_text('{"foo": 1}', encoding='utf-8')
    catalog = build_catalog([
        ResolvedSource(source=str(tmp_path), id='regras')
    ])
    entry = resolve_entries(catalog, ['notes'])[0]

    with pytest.raises(RuleInvalidError, match='notes'):
        entry.load_content()


def test_load_queued_rules_follows_zen_keys_and_skips_siblings(tmp_path: Path):
    write_graph(
        tmp_path,
        'is_asps_rec',
        ['is_impostos', 'transf_uniao/is_fpe_principal'],
    )
    write_graph(tmp_path, 'is_impostos', ['impostos/is_icms'])
    write_graph(tmp_path / 'transf_uniao', 'is_fpe_principal')
    write_graph(tmp_path / 'impostos', 'is_icms')
    write_graph(tmp_path, 'is_other')

    catalog = build_catalog([
        ResolvedSource(source=str(tmp_path), id='regras')
    ])
    entries = resolve_entries(catalog, ['regras/is_asps_rec'])
    contents = load_queued_rules(catalog, entries)

    assert set(contents['regras']) == {
        'is_asps_rec',
        'is_impostos',
        'transf_uniao/is_fpe_principal',
        'impostos/is_icms',
    }


def test_load_queued_rules_stops_on_a_cycle(tmp_path: Path):
    write_graph(tmp_path, 'parent', ['child'])
    write_graph(tmp_path, 'child', ['parent'])
    catalog = build_catalog([
        ResolvedSource(source=str(tmp_path), id='regras')
    ])
    entries = resolve_entries(catalog, ['parent'])

    contents = load_queued_rules(catalog, entries)

    assert set(contents['regras']) == {'parent', 'child'}


def test_load_queued_rules_missing_child(tmp_path: Path):
    write_graph(tmp_path, 'parent', ['missing_child'])
    catalog = build_catalog([
        ResolvedSource(source=str(tmp_path), id='regras')
    ])
    entries = resolve_entries(catalog, ['parent'])

    with pytest.raises(RuleNotFound, match='missing_child'):
        load_queued_rules(catalog, entries)


def test_load_content_rejects_broken_json(tmp_path: Path):
    (tmp_path / 'broken.json').write_text('{', encoding='utf-8')
    catalog = build_catalog([
        ResolvedSource(source=str(tmp_path), id='regras')
    ])
    entry = resolve_entries(catalog, ['broken'])[0]

    from zendt.errors import SourceError

    with pytest.raises(SourceError, match='Could not read'):
        entry.load_content()


def test_load_content_fetches_a_remote_rule(monkeypatch):
    from zendt.models import RuleEntry

    entry = RuleEntry(
        'flag',
        'rules',
        'https://example.test/flag.json',
        'flag',
        token='secret',
    )
    monkeypatch.setattr(
        'zendt.rules.catalog.request_json',
        lambda url, token: (
            {'nodes': [], 'edges': [], 'seen': token}
            if url.endswith('flag.json')
            else None
        ),
    )

    body = entry.load_content()

    assert body['seen'] == 'secret'


def test_load_queued_rules_keeps_sources_apart(tmp_path: Path):
    one = tmp_path / 'one'
    two = tmp_path / 'two'
    write_graph(one, 'is_asps_rec', ['is_impostos'])
    write_graph(one, 'is_impostos')
    write_graph(two, 'is_impostos')
    catalog = build_catalog([
        ResolvedSource(source=str(one), id='source_one'),
        ResolvedSource(source=str(two), id='source_two'),
    ])
    entries = resolve_entries(catalog, ['source_one/is_asps_rec'])

    contents = load_queued_rules(catalog, entries)

    assert set(contents) == {'source_one'}
    assert set(contents['source_one']) == {'is_asps_rec', 'is_impostos'}
