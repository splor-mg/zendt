"""Terminal layout for the interactive config editor."""

import typer

RULE = '---------'


def title(text: str) -> None:
    """Separate a block of questions and highlight its title."""
    typer.echo()
    typer.secho(f'{RULE} {text} {RULE}', bold=True, fg=typer.colors.CYAN)


def heading(text: str) -> None:
    """Highlight a short label inside a block."""
    typer.echo()
    typer.secho(text, bold=True)


def ask(text: str, **kwargs: object) -> str:
    """Ask a question on its own line.

    Typer appends ': '. A label that already ends with ':' prints '::'.
    """
    typer.echo()
    return typer.prompt(_label(text), **kwargs)


def ask_confirm(text: str, **kwargs: object) -> bool:
    """Ask a yes/no question on its own line."""
    typer.echo()
    return typer.confirm(_label(text), **kwargs)


def say(text: str, *, kind: str = 'info') -> None:
    """Print a message separated from the previous question."""
    typer.echo()
    if kind == 'error':
        typer.secho(text, fg=typer.colors.YELLOW)
        return
    if kind == 'ok':
        typer.secho(text, fg=typer.colors.GREEN)
        return
    typer.echo(text)


def _label(text: str) -> str:
    return text.rstrip().removesuffix(':').rstrip()
