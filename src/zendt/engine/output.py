"""Write the result table.

CSV uses the delimiter detected when the table was read. An omitted path
writes csv to stdout only when stdout is a pipe or a redirect. A terminal
does not receive the full table. Excel needs a file path.
"""

import sys

import pandas as pd

from zendt.engine.helpers import type_of_file
from zendt.utils.paths import resolve_path


def write_output(frame: pd.DataFrame, path: str | None) -> None:
    delimiter = frame.attrs.get('delimiter', ',')
    if not path:
        if sys.stdout.isatty():
            return
        frame.to_csv(sys.stdout, sep=delimiter, index=False)
        return
    final_path = resolve_path(path)
    ftype = type_of_file(final_path)
    if ftype == '.csv':
        frame.to_csv(final_path, sep=delimiter, index=False)
    elif ftype == '.csv.gz':
        frame.to_csv(
            final_path, sep=delimiter, compression='gzip', index=False
        )
    elif ftype == '.json':
        frame.to_json(final_path, orient='records', force_ascii=False)
    else:
        frame.to_excel(final_path, index=False)
