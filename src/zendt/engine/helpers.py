import csv
from pathlib import Path

from zendt.errors import InputError

_FORMATS = ('.csv.gz', '.json', '.csv', '.xlsx')


def detect_delimiter(sample: str) -> str:
    header = sample.splitlines()[0] if sample.strip() else ''
    try:
        dialect = csv.Sniffer().sniff(header + '\n', delimiters=',;')
        return dialect.delimiter
    except csv.Error:
        if header.count(';') > header.count(','):
            return ';'
        return ','


def type_of_file(path: str) -> str:
    name = Path(path).name.lower()
    for suffix in _FORMATS:
        if name.endswith(suffix):
            return suffix
    raise InputError(f'File format not supported: {path}')
