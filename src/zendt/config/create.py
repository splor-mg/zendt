from pathlib import Path

from zendt.config.helper import save_config
from zendt.config.ui import ask, ask_confirm, say, title
from zendt.utils.paths import is_remote


def create_source() -> dict:
    """Create a new source."""
    title('Source')
    source_id = ask('Enter a unique name for your source (ID)')
    source_location = ask('Enter the source location (local path or git URL)')

    if is_remote(source_location):
        is_private = ask_confirm('Is this a private repository?')
        if is_private:
            source_authentication = ask(
                'Enter the name of the environment variable for the '
                'authentication token [do not enter the token]'
            )
        else:
            source_authentication = None

        version = ask_confirm(
            'Would you like to specify a version for this source? '
            'If no, the ref in the URL is used, or HEAD when the URL '
            'has none.'
        )
        if version:
            source_version = ask('Enter the source version')
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
        say(
            "Source id is required and cannot contain '/'. "
            'Source was not added.',
            kind='error',
        )
        return False
    if any(item.get('id') == source_id for item in sources):
        say(
            f"Source '{source_id}' already exists. Source was not added.",
            kind='error',
        )
        return False
    sources.append(source)
    return True


def create_flow() -> dict:
    """Create a new flow."""
    title('Flow')
    flow_id = ask('Enter a unique name for your flow (ID)')
    flow_description = ask('Describe your flow in a few words')

    flow_rules = [
        rule.strip()
        for rule in ask(
            'Enter the rule(s) for your flow, comma separated'
        ).split(',')
    ]

    input_file = ask_confirm(
        'Would you like to specify a input file for your flow? '
        'Accepted formats: csv, csv.gz, xlsx, json'
    )
    if input_file:
        flow_input = ask('Flow Input Path [example: data/input.csv]')
    else:
        flow_input = None

    output_file = ask_confirm(
        'Would you like to specify a output file for your flow? '
        'Accepted formats: csv, csv.gz, xlsx, json'
    )
    if output_file:
        flow_output = ask('Flow Output Path [example: data/output.csv]')
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
        say('Flow id is required. Flow was not added.', kind='error')
        return False
    if any(item.get('id') == flow_id for item in flows):
        say(
            f"Flow '{flow_id}' already exists. Flow was not added.",
            kind='error',
        )
        return False
    flow['rules'] = [rule for rule in flow.get('rules') or [] if rule]
    if not flow['rules']:
        say(
            'A flow needs at least one rule. Flow was not added.',
            kind='error',
        )
        return False
    flows.append(flow)
    return True


def create_config() -> None:
    """Create a new config file."""

    path = Path.cwd() / 'zendt.json'
    if path.exists():
        if not ask_confirm(
            f'Config file already exists at {path}. '
            'Would you like to overwrite it?'
        ):
            say('Config file not overwritten.')
            return

    config = {
        'sources': [],
        'flows': [],
    }

    while True:
        if take_source(config['sources'], create_source()):
            if not ask_confirm('Do you want to add another source?'):
                break

    if ask_confirm('Would you like to create a flow?'):
        while True:
            if take_flow(config['flows'], create_flow()):
                if not ask_confirm('Do you want to add another flow?'):
                    break

    save_config(config)
