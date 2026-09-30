import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from zendt.errors import AuthError, SourceError
from zendt.models import ResolvedSource, SourceConfig
from zendt.rules.configs import get_source, load_default_config
from zendt.utils.env import get_env_var
from zendt.utils.paths import is_remote, resolve_path

GITHUB_HOSTS = {'github.com', 'www.github.com'}
AUTH_FAILURE = {401, 403}
_MIN_REPO_PARTS = 2
_MIN_RAW_PARTS = 3
_MIN_GIT_REF_PARTS = 2
# scp-like SSH form: git@github.com:owner/repo.git
_GIT_SCP = re.compile(
    r'^git@(?P<host>[^:/]+):(?P<owner>[^/]+)/(?P<repo>[^/]+)/?$'
)


def auth_headers(token: str | None) -> dict[str, str]:
    if not token:
        return {}
    return {'Authorization': f'Bearer {token}'}


def parse_github(url: str) -> dict | None:
    scp = _GIT_SCP.fullmatch(url.strip())
    if scp:
        if scp.group('host').lower() not in GITHUB_HOSTS:
            return None
        repo = scp.group('repo')
        if repo.endswith('.git'):
            repo = repo[:-4]
        if not repo:
            return None
        return {
            'host': 'github',
            'owner': scp.group('owner'),
            'repo': repo,
            'ref': None,
            'path': '',
        }

    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    parts = [p for p in parsed.path.strip('/').split('/') if p]
    if parts and parts[-1].endswith('.git'):
        parts[-1] = parts[-1][:-4]

    if host == 'raw.githubusercontent.com':
        if len(parts) < _MIN_RAW_PARTS:
            return None
        owner, repo, ref, *rest = parts
        return {
            'host': 'github',
            'owner': owner,
            'repo': repo,
            'ref': ref,
            'path': '/'.join(rest),
        }

    if host not in GITHUB_HOSTS:
        return None
    if len(parts) < _MIN_REPO_PARTS:
        return None
    owner, repo = parts[0], parts[1]
    rest = parts[2:]
    ref = None
    path = ''
    if rest and rest[0] in {'tree', 'blob'}:
        if len(rest) < _MIN_GIT_REF_PARTS:
            return None
        ref = rest[1]
        path = '/'.join(rest[2:])
    return {
        'host': 'github',
        'owner': owner,
        'repo': repo,
        'ref': ref,
        'path': path,
    }


def find_remote(url: str, auth: str | None = None) -> str:
    """Probe a remote URL. `auth` is the token itself, not the env var name."""
    try:
        response = requests.get(
            url,
            headers=auth_headers(auth),
            timeout=10,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise SourceError(f'Could not reach remote source: {exc}') from exc
    if response.status_code in AUTH_FAILURE:
        raise AuthError('Authentication failed. Token is invalid or expired.')
    if not response.ok:
        raise SourceError(
            f'Remote source is not accessible '
            f'(HTTP {response.status_code}): {url}'
        )
    return url


def find_local(path_str: str) -> str:
    path = Path(resolve_path(path_str))
    if not path.exists():
        raise SourceError(f'Path not found: {path}')
    if not path.is_file() and not path.is_dir():
        raise SourceError(f'Source is not a file or directory: {path}')
    return str(path)


def token_ref(auth_var: str | None) -> str | None:
    return get_env_var(auth_var) if auth_var else None


def find_source_from_config(
    source: SourceConfig, version_arg: str | None, auth_var: str | None
) -> ResolvedSource:
    return ResolvedSource(
        source=source.source,
        token=token_ref(auth_var or source.authentication),
        version=version_arg if version_arg is not None else source.version,
        id=source.id,
    )


def resolve_sources(
    source_arg: str | None,
    version_arg: str | None = None,
    auth_var: str | None = None,
) -> list[ResolvedSource]:
    """Map CLI --source to one or more sources.

    Omitted → zendt.json, else env `config`, else env `sources`.
    Specified → GitHub URL, local path, or a source id.
    A config file is never passed here; it is named by the `config` env var.
    """

    if source_arg is None:
        config = load_default_config()
        return [
            find_source_from_config(source, version_arg, auth_var)
            for source in config.sources
        ]

    if is_remote(source_arg):
        return [
            ResolvedSource(
                source=source_arg,
                token=token_ref(auth_var),
                version=version_arg,
            )
        ]

    path = Path(resolve_path(source_arg))
    if path.exists() and (path.is_dir() or path.is_file()):
        return [
            ResolvedSource(
                source=str(path.resolve()),
                token=token_ref(auth_var),
                version=version_arg,
            )
        ]

    config = load_default_config()
    source = get_source(config, source_arg)
    return [find_source_from_config(source, version_arg, auth_var)]
