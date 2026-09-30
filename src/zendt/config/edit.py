import json
from pathlib import Path

import typer

from zendt.config.create import (
    create_flow,
    create_source,
    take_flow,
    take_source,
)
from zendt.config.helper import save_config
from zendt.utils.paths import is_remote


def open_config() -> dict | None:
    """Load zendt.json from the current directory."""
    path = Path.cwd() / 'zendt.json'
    if not path.exists():
        typer.echo(
            'Config file not found. Please create it first using '
            "'zendt config --create'."
        )
        return None
    try:
        config = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        typer.echo(f'Error loading config file: {exc}')
        return None

    if not isinstance(config, dict) or not isinstance(
        config.get('sources'), list
    ):
        typer.echo("Config file is missing a 'sources' array.")
        return None
    if 'flows' not in config:
        config['flows'] = []
    elif not isinstance(config['flows'], list):
        typer.echo("Config file 'flows' must be an array.")
        return None
    return config


def edit_config() -> None:
    """Edit sources and flows in zendt.json."""
    config = open_config()
    if config is None:
        return

    while True:
        typer.echo('What would you like to edit?')
        typer.echo('1. Sources')
        typer.echo('2. Flows')
        typer.echo('3. Save and exit')
        choice = typer.prompt('Enter your choice').strip()
        if choice == '1':
            edit_sources(config)
        elif choice == '2':
            edit_flows(config)
        elif choice == '3':
            if save_config(config):
                return
        else:
            typer.echo('Invalid choice.')


def edit_sources(config: dict) -> None:
    """Create, delete, or edit a source."""
    list_items(config['sources'], 'sources')
    typer.echo('1. Create')
    typer.echo('2. Delete')
    typer.echo('3. Edit')
    typer.echo('4. Back')
    choice = typer.prompt('Enter your choice').strip()
    if choice == '1':
        add_source(config)
    elif choice == '2':
        delete_by_id(config['sources'], 'source', keep_one=True)
    elif choice == '3':
        edit_source(config)
    elif choice == '4':
        return
    else:
        typer.echo('Invalid choice.')


def edit_flows(config: dict) -> None:
    """Create, delete, or edit a flow."""
    list_items(config['flows'], 'flows')
    typer.echo('1. Create')
    typer.echo('2. Delete')
    typer.echo('3. Edit')
    typer.echo('4. Back')
    choice = typer.prompt('Enter your choice').strip()
    if choice == '1':
        add_flow(config)
    elif choice == '2':
        delete_by_id(config['flows'], 'flow')
    elif choice == '3':
        edit_flow(config)
    elif choice == '4':
        return
    else:
        typer.echo('Invalid choice.')


def list_items(items: list[dict], kind: str) -> None:
    if not items:
        typer.echo(f'No {kind} yet.')
        return
    typer.echo(f'Current {kind}:')
    for item in items:
        item_id = item.get('id', '?')
        if kind == 'sources':
            typer.echo(f'  {item_id}: {item.get("source", "")}')
        else:
            rules = ', '.join(item.get('rules') or [])
            typer.echo(f'  {item_id}: {rules}')


def find_by_id(items: list[dict], item_id: str) -> dict | None:
    for item in items:
        if item.get('id') == item_id:
            return item
    return None


def add_source(config: dict) -> None:
    take_source(config['sources'], create_source())


def add_flow(config: dict) -> None:
    take_flow(config['flows'], create_flow())


def delete_by_id(
    items: list[dict], kind: str, *, keep_one: bool = False
) -> None:
    item_id = typer.prompt(f'Enter the {kind} ID').strip()
    item = find_by_id(items, item_id)
    if item is None:
        typer.echo(f'{kind.capitalize()} not found.')
        return
    if keep_one and len(items) <= 1:
        typer.echo(
            'At least one source is required. Add another source '
            'before deleting this one.'
        )
        return
    if not typer.confirm(f"Delete {kind} '{item_id}'?"):
        typer.echo(f'{kind.capitalize()} was not deleted.')
        return
    items.remove(item)


def prompt_keep(
    label: str, current: str | None, *, allow_clear: bool = False
) -> str | None:
    """Ask for a new value. Enter keeps the current one.

    '-' clears optional fields.
    """
    shown = current if current else '(none)'
    hint = "enter to keep, '-' to clear" if allow_clear else 'enter to keep'
    value = typer.prompt(
        f'{label} [{hint}: {shown}]',
        default=current or '',
        show_default=False,
    ).strip()
    if allow_clear and value == '-':
        return None
    if not value:
        return current
    return value


def set_optional(item: dict, key: str, value: str | None) -> None:
    if value:
        item[key] = value
    else:
        item.pop(key, None)


def edit_source(config: dict) -> None:
    source_id = typer.prompt('Enter the source ID').strip()
    source = find_by_id(config['sources'], source_id)
    if source is None:
        typer.echo('Source not found.')
        return

    typer.echo(f'Editing source {source_id}...')
    location = prompt_keep('Source location', source.get('source'))
    if not location:
        typer.echo('Source location is required. This source was not changed.')
        return
    source['source'] = location

    if not is_remote(location):
        had_remote_fields = 'authentication' in source or 'version' in source
        source.pop('authentication', None)
        source.pop('version', None)
        if had_remote_fields:
            typer.echo(
                'Authentication and version were removed because '
                'this source is local.'
            )
        return

    authentication = prompt_keep(
        'Source authentication (env var name, not the token)',
        source.get('authentication'),
        allow_clear=True,
    )
    version = prompt_keep(
        'Source version', source.get('version'), allow_clear=True
    )
    set_optional(source, 'authentication', authentication)
    set_optional(source, 'version', version)


def edit_flow(config: dict) -> None:
    flow_id = typer.prompt('Enter the flow ID').strip()
    flow = find_by_id(config['flows'], flow_id)
    if flow is None:
        typer.echo('Flow not found.')
        return

    typer.echo(f'Editing flow {flow_id}...')
    description = prompt_keep(
        'Description', flow.get('description'), allow_clear=True
    )
    rules_value = prompt_keep(
        'Rules (comma separated)', ', '.join(flow.get('rules') or [])
    )
    rules = [
        part.strip() for part in (rules_value or '').split(',') if part.strip()
    ]
    if not rules:
        typer.echo(
            'A flow needs at least one rule. This flow was not changed.'
        )
        return
    set_optional(flow, 'description', description)
    flow['rules'] = rules
    flow_input = prompt_keep(
        'Input path', flow.get('input'), allow_clear=True
    )
    flow_output = prompt_keep(
        'Output path', flow.get('output'), allow_clear=True
    )
    set_optional(flow, 'input', flow_input)
    set_optional(flow, 'output', flow_output)
