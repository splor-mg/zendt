# Input and output

`apply` and `flow` read one table, evaluate it, and write one table. The whole input is loaded into memory before evaluation starts.

## Input

`--input` / `-i` is a path. On `flow`, the flag replaces the flow's `input`. When both are omitted, the command reads stdin.

| Form | How it is read |
| --- | --- |
| `.csv` | CSV. The delimiter is detected from the header. |
| `.csv.gz` | Gzip-compressed CSV, with the same delimiter detection. |
| `.json` | One JSON object is one row. A JSON array of objects is one row per object. |
| `.xlsx` | The first sheet, through pandas and openpyxl. |
| Anything else | `InputError`: file format not supported. |

_OBS: Relative paths are resolved against the current directory._

### Delimiter

For CSV, the first line is inspected. The detector chooses `,` or `;`. If the line cannot be sniffed, the delimiter is `;` when that character is more common than `,`, and `,` otherwise. An empty sample uses `,`.

That choice is stored on the table and reused when the result is written as CSV or `.csv.gz`. JSON and Excel inputs are stored with delimiter `,`, which matters only if you later write CSV.

Values are not rewritten. A semicolon file that contains `1.234,56` is kept as text. zendt does not parse decimal commas into numbers.

### Stdin

Stdin is used when no input path was given. It expects either a JSON or a CSV stream.

- If the first non-space character is `[` or `{`, the stream is parsed as JSON.
- Otherwise the stream is parsed as CSV, with the same delimiter detection as a file.

```bash
cat customers.csv | zendt apply student_discount -s ./rules > customers-out.csv
```

## Output

`--output` / `-o` is a path. On `flow`, the flag replaces the flow's `output`.

| Form | What is written |
| --- | --- |
| `.csv` | CSV, using the delimiter detected on input, without the pandas index |
| `.csv.gz` | The same CSV, gzip-compressed |
| `.json` | A JSON array of objects, UTF-8, not escaped to ASCII |
| `.xlsx` | A workbook written by pandas through openpyxl. |
| Anything else | `InputError`: file format not supported |

When no output path was given:

- If stdout is a terminal, nothing is written. The table is not dumped into the terminal.
- If stdout is a pipe or a redirect, the full CSV is written to stdout with the input delimiter.

### Preview

`--printhead` / `-ph` prints the first five rows after a successful evaluation.

- On a terminal, the preview goes to stdout.
- When stdout is a pipe or a redirect, the preview goes to stderr, so the CSV on stdout is only the result.

`--printhead` does not change the file or the CSV stream. It is not a substitute for `--output`.

## What is not checked

zendt does not check that the table has the columns or types a rule expects. A missing field fails inside the rule, row by row, as an `EngineError`. If a rule depends on a specific shape, validate or reshape the table before the command, or describe that shape in the graph. See [Recommendations](recommendations.md).
