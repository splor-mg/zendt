import json
import os
from pathlib import Path

import yaml

from zendt.errors import ConfigError
from zendt.models import FlowConfig, SourceConfig, ZendtConfig
from zendt.utils.paths import resolve_maybe_path

SOURCE_REQUIRED = {'id', 'source'}
SOURCE_ALLOWED = {'id', 'source', 'authentication', 'version'}
FLOW_REQUIRED = {'id', 'rules'}
FLOW_ALLOWED = {'id', 'description', 'input', 'rules', 'output'}


def find_config(
    start: Path | None = None, file_name: str = 'zendt.json'
) -> Path | None:
    if start is None:
        start = Path.cwd()
    config_file = start / file_name
    if config_file.exists():
        return config_file
    return None


def flatten_block(block: object) -> dict:
    if isinstance(block, dict):
        return block
    if isinstance(block, list):
        merged: dict = {}
        for item in block:
            if isinstance(item, dict):
                merged.update(item)
        return merged
    return {}


def extract_sources_and_flows(raw: object) -> dict:
    """Keep only sources and flows.

    Nested `zendt_config` (dict or list of maps) is flattened.
    """
    if not isinstance(raw, dict):
        raise ConfigError(
            'Config structure is invalid: there must be a single '
            'object at the root.'
        )

    payload: dict = {}
    if 'sources' in raw:
        payload['sources'] = raw['sources']
    if 'flows' in raw:
        payload['flows'] = raw['flows']

    if 'zendt_config' in raw and (
        'sources' not in payload or 'flows' not in payload
    ):
        nested = flatten_block(raw['zendt_config'])
        if 'sources' not in payload and 'sources' in nested:
            payload['sources'] = nested['sources']
        if 'flows' not in payload and 'flows' in nested:
            payload['flows'] = nested['flows']

    return payload


def pick_fields(item: dict, allowed: set[str]) -> dict:
    return {key: item[key] for key in allowed if key in item}


def check_ids(source_ids: list, flow_ids: list) -> None:
    if any(
        not isinstance(source_id, str) or not source_id
        for source_id in source_ids
    ):
        raise ConfigError(
            'Config structure is invalid: Source id is required.'
        )
    if len(source_ids) != len(set(source_ids)):
        raise ConfigError(
            'Config structure is invalid: Source ids are not unique.'
        )
    for source_id in source_ids:
        if '/' in source_id:
            raise ConfigError(
                'Config structure is invalid: Source id '
                f"'{source_id}' cannot contain '/'."
            )

    if any(
        not isinstance(flow_id, str) or not flow_id for flow_id in flow_ids
    ):
        raise ConfigError('Config structure is invalid: Flow id is required.')
    if len(flow_ids) != len(set(flow_ids)):
        raise ConfigError(
            'Config structure is invalid: Flow ids are not unique.'
        )


def unique_id_check(config: ZendtConfig) -> None:
    check_ids(
        [source.id for source in config.sources],
        [flow.id for flow in config.flows],
    )


def validate_parameters(raw: dict) -> None:
    """Validate the dict *before* building SourceConfig / FlowConfig."""
    if not isinstance(raw, dict):
        raise ConfigError(
            'Config structure is invalid: there must be a single '
            'object at the root.'
        )
    if 'sources' not in raw:
        raise ConfigError('Config structure is invalid: sources are missing.')
    if not isinstance(raw['sources'], list):
        raise ConfigError(
            "Config structure is invalid: 'sources' must be an array."
        )
    if not raw['sources']:
        raise ConfigError('Config structure is invalid: no sources found.')
    if 'flows' in raw and not isinstance(raw['flows'], list):
        raise ConfigError(
            "Config structure is invalid: 'flows' must be an array."
        )

    for source in raw['sources']:
        if not isinstance(source, dict):
            raise ConfigError(
                'Config structure is invalid: each source must be an object.'
            )
        actual = set(pick_fields(source, SOURCE_ALLOWED).keys())
        missing = SOURCE_REQUIRED - actual
        if missing:
            raise ConfigError(
                'Config structure is invalid: Source is missing '
                f'required parameters ({sorted(missing)}).'
            )

    for flow in raw.get('flows') or []:
        if not isinstance(flow, dict):
            raise ConfigError(
                'Config structure is invalid: Each flow must be an object.'
            )
        actual = set(pick_fields(flow, FLOW_ALLOWED).keys())
        missing = FLOW_REQUIRED - actual
        if missing:
            raise ConfigError(
                'Config structure is invalid: Flow is missing '
                f'required parameters ({sorted(missing)}).'
            )
        rules = flow.get('rules')
        names = (
            [rule for rule in rules if isinstance(rule, str) and rule.strip()]
            if isinstance(rules, list)
            else []
        )
        if not names:
            raise ConfigError(
                'Config structure is invalid: Flow '
                f"'{flow.get('id', '?')}' must have a non-empty "
                'rules list.'
            )

    check_ids(
        [source.get('id') for source in raw['sources']],
        [flow.get('id') for flow in raw.get('flows') or []],
    )


def build_config(raw: dict, base_dir: Path) -> ZendtConfig:
    payload = extract_sources_and_flows(raw)
    payload.setdefault('flows', [])
    validate_parameters(payload)

    sources = []
    for source in payload['sources']:
        fields = pick_fields(source, SOURCE_ALLOWED)
        fields['source'] = resolve_maybe_path(fields['source'], base_dir)
        sources.append(SourceConfig(**fields))

    flows = []
    for flow in payload['flows']:
        fields = pick_fields(flow, FLOW_ALLOWED)
        fields['input'] = resolve_maybe_path(fields.get('input'), base_dir)
        fields['output'] = resolve_maybe_path(fields.get('output'), base_dir)
        flows.append(FlowConfig(**fields))

    config = ZendtConfig(sources, flows)
    unique_id_check(config)
    return config


def parse_config_file(path: Path) -> dict:
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError as exc:
        raise ConfigError(
            f"Configuration file not found at '{path}'."
        ) from exc

    suffix = path.suffix.lower()
    try:
        if suffix == '.json':
            raw = json.loads(text)
        elif suffix in {'.yaml', '.yml'}:
            raw = yaml.safe_load(text)
        else:
            raise ConfigError(
                f"Unsupported configuration file type: '{path}'."
            )
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f'Invalid JSON in configuration file: {exc}'
        ) from exc
    except yaml.YAMLError as exc:
        raise ConfigError(
            f'Invalid YAML in configuration file: {exc}'
        ) from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(
            'Config structure is invalid: there must be a single '
            'object at the root.'
        )
    return raw


def sources_from_env(parsed: object) -> list:
    """One source object, or an array of them.

    Flows belong in the `flows` variable.
    """
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        if (
            'sources' in parsed
            or 'flows' in parsed
            or 'zendt_config' in parsed
        ):
            raise ConfigError(
                "Environment variable 'sources' must be one source "
                'object or a JSON array of sources, without flows. '
                "Put flows in the 'flows' environment variable."
            )
        return [parsed]
    raise ConfigError(
        "Environment variable 'sources' must be one source "
        'object or a JSON array of sources.'
    )


def load_config_from_env() -> ZendtConfig | None:
    """Read env `config`, else `sources` plus optional `flows`.

    None if neither is set.
    """
    config_var = os.environ.get('config') or os.environ.get('CONFIG')
    sources_var = os.environ.get('sources') or os.environ.get('SOURCES')
    flows_var = os.environ.get('flows') or os.environ.get('FLOWS')

    if config_var:
        resolved = resolve_maybe_path(config_var, Path.cwd())
        if resolved is None:
            return None
        path = Path(resolved)
        return build_config(parse_config_file(path), path.parent)

    if not sources_var:
        return None

    try:
        parsed = json.loads(sources_var)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Invalid JSON in environment variable 'sources': {exc}"
        ) from exc

    raw: dict = {'sources': sources_from_env(parsed)}
    if flows_var:
        try:
            raw['flows'] = json.loads(flows_var)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"Invalid JSON in environment variable 'flows': {exc}"
            ) from exc

    return build_config(raw, Path.cwd())


def load_default_config() -> ZendtConfig:
    """zendt.json first, then env `config`, then env `sources`."""
    path = find_config()
    if path is not None:
        return load_config(path)

    env_config = load_config_from_env()
    if env_config is not None:
        return env_config

    raise ConfigError(
        "No source configuration found. Set the 'config' or "
        "'sources' environment variable, create zendt.json or a "
        'personalized configuration file, or pass --source.'
    )


def load_config(path: Path | None = None) -> ZendtConfig:
    if path is None:
        path = find_config()
    if path is None:
        raise ConfigError('Configuration file not found.')

    path = Path(path)
    raw = parse_config_file(path)
    return build_config(raw, path.parent)


def get_source(config: ZendtConfig, id: str) -> SourceConfig:
    for source in config.sources:
        if source.id == id:
            return source
    raise ConfigError(f'Source with id {id} not found.')


def get_flow(config: ZendtConfig, id: str) -> FlowConfig:
    for flow in config.flows:
        if flow.id == id:
            return flow
    raise ConfigError(f'Flow with id {id} not found.')
