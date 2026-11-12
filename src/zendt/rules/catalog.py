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

from zendt.errors import (
    AmbiguousRule,
    AuthError,
    RateLimitError,
    RuleNotFound,
    SourceError,
    SourceUnavailable,
)
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
METADATA_FILENAMES = (
    'meta.json',
    '_meta.json',
    'metadata.json',
    '_metadata.json',
)


def skipped_json(name: str) -> bool:
    """Config and metadata files are not rules."""
    return name == CONFIG_FILENAME or name in METADATA_FILENAMES


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


_REQUEST_TIMEOUT = 10
_FORBIDDEN = 403
_TOO_MANY_REQUESTS = 429
_GATEWAY_ERRORS = {502, 503, 504}
_REMOTE_LIMIT = (
    'Remote repository exceeds GitHub API limits for remote reading.'
)


class _ContentsTooLarge(Exception):
    """Contents API refused this directory because it has too many entries."""


def github_headers(token: str | None) -> dict[str, str]:
    return {**auth_headers(token), 'Accept': 'application/json'}


def github_payload(response: requests.Response, url: str):
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


def github_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ''
    if not isinstance(payload, dict):
        return ''
    message = payload.get('message')
    if not isinstance(message, str):
        return ''
    return message


def rate_limited(response: requests.Response) -> bool:
    """Primary limit, secondary limit, and HTTP 429.

    A generic 403 stays an authentication failure.
    """
    if response.status_code == _TOO_MANY_REQUESTS:
        return True
    if response.status_code != _FORBIDDEN:
        return False
    text = github_message(response).lower()
    return 'api rate limit exceeded' in text or 'secondary rate limit' in text


def raise_for_github(
    response: requests.Response,
    url: str,
    *,
    directory_listing: bool,
) -> None:
    status = response.status_code
    if status in _GATEWAY_ERRORS:
        raise SourceUnavailable(
            f'GitHub is temporarily unavailable (HTTP {status}).'
        )
    if rate_limited(response):
        raise RateLimitError('GitHub API rate limit exceeded.')
    if directory_listing and contents_too_large(response):
        raise _ContentsTooLarge()
    if status in AUTH_FAILURE:
        raise AuthError(
            f'Remote source {url} requires authentication or the '
            'token is invalid.'
        )
    if not response.ok:
        raise SourceError(
            f'Could not fetch remote source {url}: (HTTP {status}).'
        )


def contents_too_large(response: requests.Response) -> bool:
    """Contents API rejects a directory above 1,000 entries with HTTP 403."""
    if response.status_code != _FORBIDDEN:
        return False
    text = github_message(response).lower()
    return 'too large' in text or 'trees api' in text


def request_json(url: str, token: str | None, params: dict | None = None):
    try:
        response = requests.get(
            url,
            headers=github_headers(token),
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SourceError(f'Could not fetch remote source: {exc}') from exc
    return github_payload(response, url)


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
        if skipped_json(file.name):
            continue
        if root is None:
            key = file.stem
        else:
            key = zen_key(file.relative_to(root).as_posix())
        add_rule(rules, file.stem, RuleLocation(str(file), key))
    return rules


class _GitHubCatalog:
    """List JSON rules one directory at a time.

    The branch, tag, or `HEAD` is resolved to one commit SHA before any
    listing. Every later request uses that SHA. A directory the Contents
    API rejects for size is read with the git tree of that directory only.
    """

    def __init__(
        self,
        info: dict,
        token: str | None,
        ref: str,
        source_prefix: str,
    ) -> None:
        self.info = info
        self.token = token
        self.ref = ref
        self.source_prefix = source_prefix
        self.commit_sha = ''
        self.root_tree_sha = ''
        self.rules: dict[str, RuleLocation] = {}
        self.seen: set[str] = set()

    def build(self) -> dict[str, RuleLocation]:
        self.resolve_commit()
        self.collect(self.source_prefix, None)
        return self.rules

    def repo_url(self) -> str:
        return (
            f'https://api.github.com/repos/{self.info["owner"]}/'
            f'{self.info["repo"]}'
        )

    def contents_url(self, path: str) -> str:
        base = f'{self.repo_url()}/contents'
        if not path:
            return base
        return f'{base}/{quote(path, safe="/")}'

    def commit_url(self) -> str:
        ref = quote(self.ref, safe='')
        return f'{self.repo_url()}/commits/{ref}'

    def tree_url(self, tree_sha: str) -> str:
        sha = quote(str(tree_sha), safe='')
        return f'{self.repo_url()}/git/trees/{sha}'

    def _get(self, url: str, params: dict | None) -> requests.Response:
        return requests.get(
            url,
            headers=github_headers(self.token),
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )

    def github_json(
        self,
        url: str,
        params: dict | None = None,
        *,
        directory_listing: bool = False,
    ):
        try:
            response = self._get(url, params)
        except requests.Timeout as exc:
            raise SourceUnavailable(
                'GitHub is temporarily unavailable.'
            ) from exc
        except requests.RequestException as exc:
            raise SourceError(f'Could not fetch remote source: {exc}') from exc
        raise_for_github(response, url, directory_listing=directory_listing)
        return response.json()

    def resolve_commit(self) -> None:
        payload = self.github_json(self.commit_url())
        if not isinstance(payload, dict):
            raise SourceError('Unexpected GitHub commit response.')
        sha = payload.get('sha')
        commit = payload.get('commit') if isinstance(payload, dict) else None
        tree = commit.get('tree') if isinstance(commit, dict) else None
        tree_sha = tree.get('sha') if isinstance(tree, dict) else None
        if not sha or not tree_sha:
            raise SourceError('Unexpected GitHub commit response.')
        self.commit_sha = str(sha)
        self.root_tree_sha = str(tree_sha)

    def fetch_contents(self, path: str) -> list:
        payload = self.github_json(
            self.contents_url(path),
            {'ref': self.commit_sha},
            directory_listing=True,
        )
        if isinstance(payload, dict):
            return [payload]
        if not isinstance(payload, list):
            raise SourceError('Unexpected GitHub contents response.')
        return payload

    def tree_payload(self, tree_sha: str, *, recursive: bool) -> dict:
        params = {'recursive': '1'} if recursive else None
        payload = self.github_json(self.tree_url(tree_sha), params)
        if not isinstance(payload, dict):
            raise SourceError('Unexpected GitHub trees response.')
        if payload.get('truncated'):
            raise SourceError(_REMOTE_LIMIT)
        return payload

    def collect(self, directory: str, tree_sha: str | None) -> None:
        if directory in self.seen:
            return
        self.seen.add(directory)
        try:
            entries = self.fetch_contents(directory)
        except _ContentsTooLarge:
            sha = tree_sha or self.lookup_tree_sha(directory)
            self.read_directory_tree(sha, directory)
            return
        for item in entries:
            self.add_contents_item(item)

    def add_contents_item(self, item: object) -> None:
        if not isinstance(item, dict):
            return
        path = item.get('path') or ''
        kind = item.get('type')
        if kind == 'dir' and path:
            sha = item.get('sha')
            self.collect(path, str(sha) if sha else None)
            return
        if kind == 'file' and path:
            self.add_blob(path)

    def lookup_tree_sha(self, directory: str) -> str:
        parts = [part for part in directory.split('/') if part]
        if not parts:
            return self.root_tree_sha
        payload = self.tree_payload(self.root_tree_sha, recursive=False)
        sha = ''
        for index, part in enumerate(parts):
            sha = self.child_sha(payload, part, directory)
            if index < len(parts) - 1:
                payload = self.tree_payload(sha, recursive=False)
        return sha

    def child_sha(self, payload: dict, part: str, directory: str) -> str:
        for item in payload.get('tree') or []:
            if item.get('path') != part or item.get('type') != 'tree':
                continue
            sha = item.get('sha')
            if sha:
                return str(sha)
        raise SourceError(
            f'Could not resolve directory {directory} at {self.commit_sha}.'
        )

    def read_directory_tree(self, tree_sha: str, directory: str) -> None:
        payload = self.tree_payload(tree_sha, recursive=True)
        self.add_recursive_blobs(payload, directory)

    def add_recursive_blobs(self, payload: dict, directory: str) -> None:
        for item in payload.get('tree') or []:
            if item.get('type') != 'blob':
                continue
            name = item.get('path') or ''
            if not name:
                continue
            full = f'{directory}/{name}' if directory else name
            self.add_blob(full)

    def add_blob(self, blob_path: str) -> None:
        if not blob_path.lower().endswith(JSON_SUFFIX):
            return
        if skipped_json(Path(blob_path).name):
            return
        if not under_prefix(blob_path, self.source_prefix):
            return
        prefix = self.source_prefix
        relative = (
            blob_path[len(prefix) :].lstrip('/') if prefix else blob_path
        )
        add_rule(
            self.rules,
            Path(blob_path).stem,
            RuleLocation(
                github_raw_url(self.info, self.commit_sha, blob_path),
                zen_key(relative),
            ),
        )


def catalog_github_tree(
    info: dict, token: str | None, version: str | None
) -> dict[str, RuleLocation]:
    ref = str(version or info.get('ref') or 'HEAD')
    source_prefix = (info.get('path') or '').strip('/')
    return _GitHubCatalog(info, token, ref, source_prefix).build()


def commit_sha(info: dict, token: str | None, ref: str) -> str:
    """Resolve a ref to one commit SHA.

    A tag or branch such as `relatorios/v0.1.0` cannot sit in a raw
    URL: the slash is a path separator. The commit lookup percent-encodes
    that slash, and the SHA is unambiguous afterwards.
    """
    catalog = _GitHubCatalog(info, token, ref, '')
    catalog.resolve_commit()
    return catalog.commit_sha


def catalog_remote(
    url: str, token: str | None, version: str | None
) -> dict[str, RuleLocation]:
    github = parse_github(url)
    if github:
        path = github.get('path') or ''
        if path.lower().endswith(JSON_SUFFIX):
            ref = str(version or github.get('ref') or 'HEAD')
            if '/' in ref:
                ref = commit_sha(github, token, ref)
            name = Path(path).stem
            return {
                name: RuleLocation(github_raw_url(github, ref, path), name)
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
