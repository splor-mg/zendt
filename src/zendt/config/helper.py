import json
from pathlib import Path

import typer

from zendt.errors import ConfigError
from zendt.rules.configs import validate_parameters


def save_config(config: dict) -> bool:
    """Write zendt.json. Returns False when the file was left unchanged."""
    try:
        validate_parameters(config)
    except ConfigError as exc:
        typer.echo(str(exc))
        typer.echo('Config file was not saved.')
        return False

    path = Path.cwd() / 'zendt.json'
    try:
        path.write_text(json.dumps(config, indent=4), encoding='utf-8')
    except Exception as exc:
        typer.echo(f'Error writing config file: {exc}')
        return False
    typer.echo('Saved zendt.json.')
    return True
