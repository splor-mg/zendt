"""Read the table a command evaluates.

A path reads csv, csv.gz, xlsx, or json. No path reads stdin: `[` or `{` is
json, anything else is csv. Empty stdin, or a terminal with no pipe, is an
error. JSON is an array of objects, or one object as a single row.

Columns use nullable dtypes, so a blank cell does not turn integers into
floats.
"""

import gzip
import io
import json
import sys
from pathlib import Path

import pandas as pd

from zendt.engine.helpers import detect_delimiter, type_of_file
from zendt.errors import InputError
from zendt.utils.paths import resolve_path

_SAMPLE = 8192


def resolve_input(path: str | None) -> pd.DataFrame:
    """Read `path`, or stdin when the command did not pass one."""
    if path:
        return read_table(path)
    return read_stdin()


def read_table(path: str) -> pd.DataFrame:
    location = resolve_path(path)
    ftype = type_of_file(location)
    try:
        if ftype == '.json':
            data = json.loads(Path(location).read_text(encoding='utf-8'))
            return remember(frame_from_json(data), ',')
        if ftype == '.csv':
            return read_csv(location, text_sample(location))
        if ftype == '.csv.gz':
            return read_csv(
                location,
                text_sample(location, compressed=True),
                compressed=True,
            )
        return remember(pd.read_excel(location, dtype_backend='numpy_nullable'), ',')
    except InputError:
        raise
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise InputError(f'Could not read input: {location}') from exc


def read_stdin() -> pd.DataFrame:
    if sys.stdin.isatty():
        raise InputError(
            'No input provided. Pass --input or pipe csv or json on stdin.'
        )
    data = sys.stdin.read()
    if not data.strip():
        raise InputError('Stdin is empty.')
    if data.lstrip()[:1] in '[{':
        try:
            return remember(frame_from_json(json.loads(data)), ',')
        except json.JSONDecodeError as exc:
            raise InputError('Stdin JSON is invalid.') from exc
    try:
        delimiter = detect_delimiter(data)
        frame = pd.read_csv(
            io.StringIO(data), sep=delimiter, dtype_backend='numpy_nullable'
        )
        return remember(frame, delimiter)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InputError('Stdin is neither json nor csv.') from exc


def read_csv(path: str, sample: str, compressed: bool = False) -> pd.DataFrame:
    delimiter = detect_delimiter(sample)
    frame = pd.read_csv(
        path,
        sep=delimiter,
        compression='gzip' if compressed else None,
        dtype_backend='numpy_nullable',
    )
    return remember(frame, delimiter)


def remember(frame: pd.DataFrame, delimiter: str) -> pd.DataFrame:
    frame.attrs['delimiter'] = delimiter
    return frame


def text_sample(path: str, compressed: bool = False) -> str:
    opener = gzip.open if compressed else open
    with opener(path, 'rt', encoding='utf-8') as handle:
        return handle.read(_SAMPLE)


def frame_from_json(data: object) -> pd.DataFrame:
    if isinstance(data, dict):
        frame = pd.DataFrame([data])
    elif isinstance(data, list) and all(
        isinstance(item, dict) for item in data
    ):
        frame = pd.DataFrame(data)
    else:
        raise InputError(
            'JSON input must be an object or an array of objects.'
        )
    return frame.convert_dtypes(dtype_backend='numpy_nullable')
