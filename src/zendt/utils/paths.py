from pathlib import Path

REMOTE_PREFIXES = ('http://', 'https://', 'git@', 'ssh://')


def is_remote(value: str) -> bool:
    return value.startswith(REMOTE_PREFIXES)


def resolve_path(value: str, base: Path | None = None) -> str:
    """Keep remote URLs as-is.

    Resolve relative local paths against *base* (cwd by default).
    """
    if is_remote(value):
        return value
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    if base is None:
        base = Path.cwd()
    return str((base / path).resolve())


def resolve_maybe_path(
    value: str | None, base: Path | None = None
) -> str | None:
    if value is None:
        return None
    return resolve_path(value, base)
