import sys
from typing import Annotated

import pandas as pd
import typer

from zendt.config.create import create_config
from zendt.config.edit import edit_config
from zendt.engine.output import write_output
from zendt.errors import ZendtError
from zendt.main import apply, flow, rules_list

app = typer.Typer(
    name='zendt',
    help='Apply JDM (GoRules) rules to data from the terminal.',
    no_args_is_help=True,
)

SourceOption = typer.Option(
    None,
    '--source',
    '-s',
    help='GitHub URL, local path, or id of a configured source.',
)

FindOption = typer.Option(
    None,
    '--find',
    '-f',
    help='Search for rules whose name contains the specified word.',
)

VersionOption = typer.Option(
    None,
    '--version',
    '-v',
    help='Rule version to apply for git repositories.',
)

AuthOption = typer.Option(
    None,
    '--authentication',
    '-a',
    help=(
        'Name of the environment variable that holds the token '
        '(private repositories).'
    ),
)

InputOption = typer.Option(
    None,
    '--input',
    '-i',
    help='Input file to process.',
)

OutputOption = typer.Option(
    None,
    '--output',
    '-o',
    help='Output file to save.',
)

PrintHeadOption = typer.Option(
    False,
    '--printhead',
    '-ph',
    help='Print a preview of the result on screen.',
)

CreateConfigOption = typer.Option(
    False,
    '--create',
    '-c',
    help='Create a zendt.json configuration file.',
)

EditConfigOption = typer.Option(
    False,
    '--edit',
    '-e',
    help='Edit the zendt.json configuration file.',
)


def echo_head(frame: pd.DataFrame) -> None:
    """Preview on the terminal.

    Keep it off stdout when that stream carries the csv.
    """
    typer.echo(frame.head(), err=not sys.stdout.isatty())


@app.command('config')
def config(
    create: bool = CreateConfigOption,
    edit: bool = EditConfigOption,
) -> None:
    """Manage the zendt.json configuration file."""
    if create:
        create_config()
    elif edit:
        edit_config()


@app.command('list')
def list_rules_command(
    source: str = SourceOption,
    find: str = FindOption,
    version: str = VersionOption,
    authentication: str = AuthOption,
) -> None:
    """List the JDM rules found in SOURCE."""
    try:
        names = rules_list(source, find, version, authentication)
    except ZendtError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from exc

    typer.echo('Rules found in provided sources:')
    for name in names:
        typer.echo(name)


@app.command('apply')
def apply_command(
    rules: Annotated[
        list[str], typer.Argument(help='Names of the rules to apply.')
    ],
    source: str = SourceOption,
    authentication: str = AuthOption,
    version: str = VersionOption,
    input: str = InputOption,
    output: str = OutputOption,
    printhead: bool = PrintHeadOption,
) -> None:
    """Apply the JDM rules passed as arguments."""
    try:
        result = apply(rules, source, authentication, version, input)
        write_output(result, output)
        if printhead:
            echo_head(result)
    except ZendtError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command('flow')
def flow_command(
    flow_id: Annotated[str, typer.Argument(help='Configured flow ID.')],
    input: str = InputOption,
    output: str = OutputOption,
    printhead: bool = PrintHeadOption,
) -> None:
    """Apply a pre-configured flow."""
    try:
        result = flow(flow_id, input)
    except ZendtError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from exc

    destination = output
    if destination is None:
        destination = result.attrs.get('output')
    write_output(result, destination)
    if printhead:
        echo_head(result)
