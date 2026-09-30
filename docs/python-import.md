# Python import

Zendt is a command-line tool. The commands in [Commands](cli.md) are the primary way to list rules and apply them to a table.

The same three operations are also available as Python functions, for a program that already holds a table in memory or that needs the result as a pandas `DataFrame`. `config` stays a terminal command. Creating and editing `zendt.json` is not part of this API.

```python
from zendt import rules_list, apply, flow
```

Each function loads `.env` from the current directory first, without overriding variables that are already set. A missing rule, a bad source, or a bad config raises `ZendtError` from `zendt.errors`. The message is the same text the command would print.

## List rules

`rules_list` is the Python form of `zendt list`. It returns the rule references. It does not print them.

```python
from zendt import rules_list

names = rules_list(source='./rules')
matches = rules_list(source='./rules', find='discount')
```

`source`, `version`, and `authentication` follow the same resolution as `--source`, `-v`, and `-a`. Omit `source` to use `zendt.json`, then the `config` environment variable, then `sources`. `find` keeps references that contain the text, the same substring match as `--find`.

Each string is `source_id/name` when the source has an id, otherwise the file stem. Pass that string to `apply`, or store it in a flow. This call records names and paths. It does not read the graphs.

An empty result raises `ZendtError`: `No rules matching '…'` when `find` was set, and `No rules found in the provided sources.` otherwise.

## Apply rules

`apply` is the Python form of `zendt apply`. It returns the result table. It does not write a file.

```python
import pandas as pd
from zendt import apply

frame = pd.read_csv('customers.csv')
result = apply(
    ['student_discount', 'age_discount'],
    source='./rules',
    input=frame,
)
```

`rules` is the list of rule names, in the order the command would receive them. `source`, `version`, and `authentication` match `-s`, `-v`, and `-a`.

`input` is a file path, a `DataFrame`, or omitted. A path is read with the same formats as `--input` ([Input and output](input-output.md)). A `DataFrame` is used as it is, with no read from disk. Omitting `input` reads stdin, as the command does when `-i` is absent.

Rules run in the order given. Each rule sees the original input columns, not columns created by an earlier rule. The returned frame is the input table plus the new columns. [Evaluation](evaluation.md) describes batches, extra processes, and what happens when two rules create the same column.

## Run a flow

`flow` is the Python form of `zendt flow`. The argument is the flow id from the config, not a rule name.

```python
from zendt import flow

result = flow('financedata')
result = flow('financedata', input='customers.csv')
```

A flow has no source argument. The function loads every source in the config, using each source's own `authentication` and `version`. Pass `input` as a path or a `DataFrame` to replace the flow's `input` for this call. Omit it, and the function uses the path stored on the flow. When that field is also empty, it reads stdin.

The frame's `attrs['output']` holds the flow's configured output path, or `None` when the flow has none. The function does not write that file. To save it:

```python
result = flow('financedata')
path = result.attrs.get('output')
if path:
    result.to_csv(
        path,
        sep=result.attrs.get('delimiter', ','),
        index=False,
    )
```

`attrs['delimiter']` is the separator detected when the table was read. A `DataFrame` you passed in uses `,` unless that frame already stored one.

## What stays the same, and what changes

The resolution of sources, names, and nested decision graphs is the command's resolution. Evaluation is the same engine path.

| | CLI | Python |
| --- | --- | --- |
| List | `zendt list` prints one name per line | `rules_list` returns `list[str]` |
| Apply and flow | Write a file, or CSV on stdout | Return a `DataFrame` |
| Input | Path or stdin | Path, stdin, or a `DataFrame` |
| Flow output | `-o`, or the path in the flow, or stdout | Not written. The configured path is `result.attrs['output']` |
| Errors | Message on stderr and an exit code | `ZendtError` |
| Preview | `--printhead` | No preview |
| Config editor | `zendt config --create` and `--edit` | Not available |
