import json
from pathlib import Path

from zendt.config.ui import say
from zendt.errors import ConfigError
from zendt.rules.configs import validate_parameters


def save_config(config: dict) -> bool:
    """Write zendt.json. Returns False when the file was left unchanged."""
    try:
        validate_parameters(config)
    except ConfigError as exc:
        say(str(exc), kind='error')
        say('Config file was not saved.', kind='error')
        return False

    path = Path.cwd() / 'zendt.json'
    try:
        path.write_text(json.dumps(config, indent=4), encoding='utf-8')
    except Exception as exc:
        say(f'Error writing config file: {exc}', kind='error')
        return False
    say('Saved zendt.json.', kind='ok')
    return True
