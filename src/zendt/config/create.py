from pathlib import Path

import typer

from zendt.config.helper import save_config
from zendt.utils.paths import is_remote


def create_source() -> dict:
    """Create a new source."""
    typer.echo('Enter a unique name for your source (ID):')
    source_id = typer.prompt('Source ID')

    typer.echo('Enter the source location (local path or git URL):')
    source_location = typer.prompt('Source location')

    if is_remote(source_location):
        is_private = typer.confirm('Is this a private repository?')
        if is_private:
            typer.echo(
                'Enter the name of the environment variable for the '
                'authentication token [do not enter the token]:'
            )
            source_authentication = typer.prompt('Source Authentication')
        else:
            source_authentication = None

        version = typer.confirm(
            'Would you like to specify a version for this source? '
            'If no, the ref in the URL is used, or HEAD when the URL has none.'
        )
        if version:
            typer.echo('Enter the source version:')
            source_version = typer.prompt('Source Version')
        else:
            source_version = None
    else:
        source_authentication = None
        source_version = None

    source = {}
    source['id'] = source_id
    source['source'] = source_location
    if source_authentication:
        source['authentication'] = source_authentication
    if source_version:
        source['version'] = source_version

    return source


def take_source(sources: list[dict], source: dict) -> bool:
    """Append a source when its id is usable.

    False leaves the list unchanged.
    """
    source_id = source.get('id', '')
    if not source_id or '/' in source_id:
        typer.echo(
            "Source id is required and cannot contain '/'. "
            'Source was not added.'
        )
        return False
    if any(item.get('id') == source_id for item in sources):
        typer.echo(
            f"Source '{source_id}' already exists. Source was not added."
        )
        return False
    sources.append(source)
    return True


def create_flow() -> dict:
    """Create a new flow."""
    flow_id = typer.prompt('Enter a unique name for your flow (ID):')
    flow_description = typer.prompt('Describe your flow in a few words:')

    flow_rules = [
        rule.strip()
        for rule in typer.prompt(
            'Enter the rule(s) for your flow, comma separated:'
        ).split(',')
    ]

    input_file = typer.confirm(
        'Would you like to specify a input file for your flow? '
        'Accepted formats: csv, csv.gz, xlsx, json'
    )
    if input_file:
        flow_input = typer.prompt('Flow Input Path [example: data/input.csv]:')
    else:
        flow_input = None

    output_file = typer.confirm(
        'Would you like to specify a output file for your flow? '
        'Accepted formats: csv, csv.gz, xlsx, json'
    )
    if output_file:
        flow_output = typer.prompt(
            'Flow Output Path [example: data/output.csv]:'
        )
    else:
        flow_output = None

    flow = {}
    flow['id'] = flow_id
    flow['description'] = flow_description
    flow['rules'] = flow_rules
    if flow_input:
        flow['input'] = flow_input
    if flow_output:
        flow['output'] = flow_output

    return flow


def take_flow(flows: list[dict], flow: dict) -> bool:
    """Append a flow when its id and rules are usable.

    False leaves the list unchanged.
    """
    flow_id = flow.get('id', '')
    if not flow_id:
        typer.echo('Flow id is required. Flow was not added.')
        return False
    if any(item.get('id') == flow_id for item in flows):
        typer.echo(f"Flow '{flow_id}' already exists. Flow was not added.")
        return False
    flow['rules'] = [rule for rule in flow.get('rules') or [] if rule]
    if not flow['rules']:
        typer.echo('A flow needs at least one rule. Flow was not added.')
        return False
    flows.append(flow)
    return True


def create_config() -> None:
    """Create a new config file."""

    path = Path.cwd() / 'zendt.json'
    if path.exists():
        if not typer.confirm(
            f'Config file already exists at {path}. '
            'Would you like to overwrite it?'
        ):
            typer.echo('Config file not overwritten.')
            return

    config = {
        'sources': [],
        'flows': [],
    }

    typer.echo("Let's create the first source...")
    while True:
        if take_source(config['sources'], create_source()):
            if not typer.confirm('Do you want to add another source?'):
                break

    if typer.confirm('Would you like to create a flow?'):
        while True:
            if take_flow(config['flows'], create_flow()):
                if not typer.confirm('Do you want to add another flow?'):
                    break

    save_config(config)
