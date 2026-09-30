"""Rule catalog: names and origins, without loading JDM bodies.

catalog_rules → {name: RuleLocation} for one source.
build_catalog → one entry per (source_id, name). The same stem may
exist in two sources.

`name` is the file stem (the CLI name). `key` is the path inside the source
without `.json`, which is what a decision node asks for (`content.key`).
"""

import json
from pathlib import Path
from urllib.parse import quote

import requests

from zendt.errors import AmbiguousRule, AuthError, RuleNotFound, SourceError
from zendt.models import ResolvedSource, RuleEntry, RuleLocation
from zendt.rules.sources import (
    AUTH_FAILURE,
    auth_headers,
    find_local,
    parse_github,
)
from zendt.utils.paths import is_remote

JSON_SUFFIX = '.json'
CONFIG_FILENAME = 'zendt.json'


def zen_key(relative: str) -> str:
    """Path inside the source, without the `.json` suffix."""
    path = Path(relative)
    if path.suffix.lower() == JSON_SUFFIX:
        path = path.with_suffix('')
    return path.as_posix()


def add_rule(
    rules: dict[str, RuleLocation], name: str, location: RuleLocation
) -> None:
    if name in rules:
        raise SourceError(f"Duplicate rule name '{name}' in source.")
    rules[name] = location


def request_json(url: str, token: str | None, params: dict | None = None):
    try:
        response = requests.get(
            url,
            headers={**auth_headers(token), 'Accept': 'application/json'},
            params=params,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise SourceError(f'Could not fetch remote source: {exc}') from exc
    if response.status_code in AUTH_FAILURE:
        raise AuthError(
            f'Remote source {url} requires authentication or the '
            'token is invalid.'
        )
    if not response.ok:
        raise SourceError(
            f'Could not fetch remote source {url}: '
            f'(HTTP {response.status_code}).'
        )
    return response.json()


def under_prefix(blob_path: str, prefix: str) -> bool:
    if not prefix:
        return True
    prefix = prefix.strip('/')
    return blob_path == prefix or blob_path.startswith(prefix + '/')


def github_raw_url(info: dict, ref: str, path: str) -> str:
    return f'https://raw.githubusercontent.com/{info["owner"]}/{info["repo"]}/{ref}/{path}'


def catalog_local(path: Path) -> dict[str, RuleLocation]:
    if path.is_file():
        if path.suffix.lower() != JSON_SUFFIX:
            raise SourceError(f'Source file is not JSON: {path}')
        files = [path]
        root = None
    else:
        files = sorted(path.rglob('*.json'))
        root = path

    rules: dict[str, RuleLocation] = {}
    for file in files:
        if file.name == CONFIG_FILENAME:
            continue
        if root is None:
            key = file.stem
        else:
            key = zen_key(file.relative_to(root).as_posix())
        add_rule(rules, file.stem, RuleLocation(str(file), key))
    return rules


def catalog_github_tree(
    info: dict, token: str | None, version: str | None
) -> dict[str, RuleLocation]:
    ref = version or info.get('ref') or 'HEAD'
    url = (
        f'https://api.github.com/repos/{info["owner"]}/{info["repo"]}'
        f'/git/trees/{quote(str(ref), safe="")}'
    )
    payload = request_json(url, token, params={'recursive': '1'})
    if not isinstance(payload, dict):
        raise SourceError('Unexpected GitHub trees response.')
    if payload.get('truncated'):
        raise SourceError(
            'Remote repository tree is too large to list in one request. '
            'Pass the URL of the rules folder instead of the repository root.'
        )

    prefix = (info.get('path') or '').strip('/')
    rules: dict[str, RuleLocation] = {}
    for item in payload.get('tree') or []:
        if item.get('type') != 'blob':
            continue
        blob_path = item.get('path') or ''
        if not blob_path.lower().endswith(JSON_SUFFIX):
            continue
        if Path(blob_path).name == CONFIG_FILENAME:
            continue
        if not under_prefix(blob_path, prefix):
            continue
        relative = (
            blob_path[len(prefix) :].lstrip('/') if prefix else blob_path
        )
        add_rule(
            rules,
            Path(blob_path).stem,
            RuleLocation(
                github_raw_url(info, str(ref), blob_path), zen_key(relative)
            ),
        )
    return rules


def catalog_remote(
    url: str, token: str | None, version: str | None
) -> dict[str, RuleLocation]:
    github = parse_github(url)
    if github:
        path = github.get('path') or ''
        if path.lower().endswith(JSON_SUFFIX):
            ref = version or github.get('ref') or 'HEAD'
            name = Path(path).stem
            return {
                name: RuleLocation(
                    github_raw_url(github, str(ref), path), name
                )
            }
        return catalog_github_tree(github, token, version)

    raise SourceError(
        'Remote sources must be GitHub URLs '
        '(rules folder or a single .json file).'
    )


def catalog_rules(
    source: str,
    token: str | None = None,
    version: str | None = None,
) -> dict[str, RuleLocation]:

    if is_remote(source):
        return catalog_remote(source, token, version)
    if version:
        raise SourceError('--version is only valid for git sources.')
    path = Path(find_local(source))
    return catalog_local(path)


def build_catalog(sources: list[ResolvedSource]) -> list[RuleEntry]:
    catalog: list[RuleEntry] = []
    for item in sources:
        rules = catalog_rules(item.source, item.token, item.version)
        for name, location in rules.items():
            catalog.append(
                RuleEntry(
                    name, item.id, location.origin, location.key, item.token
                )
            )
    return catalog


def resolve_rule(catalog: list[RuleEntry], reference: str) -> RuleEntry:
    """`source_id/name` selects that source.

    A short name is valid when it appears once.
    """
    if '/' in reference:
        source_id, name = reference.split('/', 1)
        matches = [
            entry
            for entry in catalog
            if entry.source_id == source_id and entry.name == name
        ]
        if not matches:
            raise RuleNotFound(f"Rule '{reference}' not found.")
        return matches[0]

    matches = [entry for entry in catalog if entry.name == reference]
    if not matches:
        raise RuleNotFound(f"Rule '{reference}' not found.")
    if len(matches) == 1:
        return matches[0]

    where = ' and '.join(entry.source_id or entry.origin for entry in matches)
    raise AmbiguousRule(f'{reference} is in {where}. Use {matches[0].ref}.')


def read_local_json(origin: str) -> dict:
    try:
        data = json.loads(Path(origin).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceError(f'Could not read rule JSON: {origin}') from exc
    if not isinstance(data, dict):
        raise SourceError(f'Rule JSON must be an object: {origin}')
    return data
