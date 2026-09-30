import pandas as pd

from zendt.engine.evaluate import evaluate_input
from zendt.engine.input import resolve_input
from zendt.engine.load import load_queued_rules, resolve_entries
from zendt.errors import ZendtError
from zendt.rules.catalog import build_catalog
from zendt.rules.configs import get_flow, load_default_config
from zendt.rules.sources import find_source_from_config, resolve_sources
from zendt.utils.env import load_env


def load_table(data: str | pd.DataFrame | None) -> pd.DataFrame:
    """Read a path or stdin, or keep a table the caller already built."""
    if isinstance(data, pd.DataFrame):
        return data
    return resolve_input(data)


def rules_list(
    source: str | None = None,
    find: str | None = None,
    version: str | None = None,
    authentication: str | None = None,
) -> list[str]:
    """Return the JDM rule names found in the sources."""
    load_env()
    catalog = build_catalog(resolve_sources(source, version, authentication))
    names = [entry.ref for entry in catalog]
    if find is not None:
        names = [name for name in names if find in name]
    if not names:
        if find is not None:
            raise ZendtError(f"No rules matching '{find}'.")
        raise ZendtError('No rules found in the provided sources.')
    return names


def apply(
    rules: list[str],
    source: str | None = None,
    authentication: str | None = None,
    version: str | None = None,
    input: str | pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Apply the named JDM rules and return the table."""
    load_env()
    input_data = load_table(input)
    catalog = build_catalog(resolve_sources(source, version, authentication))
    entries = resolve_entries(catalog, rules)
    loaded_rules = load_queued_rules(catalog, entries)
    return evaluate_input(input_data, entries, loaded_rules)


def flow(
    flow_id: str,
    input: str | pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Apply a configured flow and return the table.

    The flow's output path is stored on ``result.attrs['output']``.
    The CLI writes that file when ``--output`` is omitted.
    """
    load_env()
    config = load_default_config()
    sources = [
        find_source_from_config(item, None, None) for item in config.sources
    ]
    chosen = get_flow(config, flow_id)
    catalog = build_catalog(sources)
    entries = resolve_entries(catalog, chosen.rules)
    loaded_rules = load_queued_rules(catalog, entries)
    data = input if input is not None else chosen.input
    result = evaluate_input(load_table(data), entries, loaded_rules)
    result.attrs['output'] = chosen.output
    return result
