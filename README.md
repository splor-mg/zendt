# zendt [Zen Engine for Data Tables]

![Coverage](https://raw.githubusercontent.com/splor-mg/zendt/refs/heads/main/coverage.svg)

Apply [GoRules](https://gorules.io/) business rules to a table from the terminal. Rules are JSON graphs in the [JDM standard](https://docs.gorules.io/developers/jdm/standard). Tables are CSV, gzip-compressed CSV, Excel (`.xlsx`), or JSON.

```bash
pip install zendt
zendt apply student_discount -s ./rules -i customers.csv -o customers-out.csv
```

The command keeps every input column and appends the columns each rule creates. Each rule sees the original rows, not columns produced by an earlier rule in the same command.

Python 3.13 or newer is required.

## Commands

```bash
zendt list -s ./rules
zendt list -s source_one -f discount
zendt apply student_discount age_discount -s ./rules -i customers.csv -o customers-out.csv
zendt apply student_discount -s https://github.com/user/rules/tree/main/rules -a GH_TOKEN -v 1.2.1 -i customers.csv
zendt flow financedata -i customers.csv -o customers-out.csv --printhead
zendt config --create
zendt config --edit
```

| Command | What it does |
| --- | --- |
| `list` | Print the rule names in a source. Does not run them. |
| `apply` | Run one or more rules on a table. |
| `flow` | Run a named pipeline from `zendt.json`. |
| `config --create` | Write `zendt.json` by answering prompts. |
| `config --edit` | Edit that file by answering prompts. |


### Flags

| Flag | Short | Use |
| --- | --- | --- |
| `--source` | `-s` | GitHub URL, local file or directory, or a source id from the config. `list` and `apply`. |
| `--find` | `-f` | On `list`, keep names that contain this text. |
| `--version` | `-v` | Git tag, branch, or other ref. `list` and `apply`. |
| `--authentication` | `-a` | Name of the environment variable that holds a GitHub token. Not the token. |
| `--input` | `-i` | Input file. Omitted means stdin. |
| `--output` | `-o` | Output file. Omitted writes CSV to stdout only when stdout is a pipe or a redirect. |
| `--printhead` | `-ph` | Print the first five result rows. On `apply` and `flow` this is not help; use `--help`. |
| `--create` | `-c` | Create `zendt.json`. |
| `--edit` | `-e` | Edit `zendt.json`. |

## A local folder of rules

```bash
zendt list -s ./rules
zendt apply student_discount -s ./rules -i customers.csv -o customers-out.csv
```

`student_discount` is the file `rules/student_discount.json`. Nested files are listed by their stem as well. A decision node inside a graph calls another file by its path relative to the folder, without `.json` (`discounts/student_discount`).

`list` prints one name per line. A file named `zendt.json` inside the rules folder is skipped.

## GitHub

```bash
export GH_TOKEN=github_pat_...
zendt apply student_discount \
  -s https://github.com/user/rules/tree/main/rules \
  -a GH_TOKEN \
  -v 1.2.1 \
  -i customers.csv \
  -o customers-out.csv
```

The URL must be GitHub: a repository, a `tree` URL of the rules folder, a `blob` URL of one JSON file, or a `raw.githubusercontent.com` URL. Other hosts are rejected.

`-v` is the git ref sent to GitHub. If you omit it, the ref in the URL is used, or `HEAD` when the URL has none. zendt does not look up the latest tag. `-a` is the name of the environment variable that stores the token for a private repository. You can also put the token in a `.env` file in the current directory. Values already set in the environment are left as they are.


## Configuration and flows

When you omit `--source`, zendt looks for `zendt.json` in the current directory, then the `config` (or `CONFIG`) environment variable, which stores the path to a config file (json or yaml), then `sources` (or `SOURCES`) env variable. `sources` is one source object or a JSON array of sources. Flows, if any, go in env variable `flows` (or `FLOWS`).

```json
{
  "sources": [
    {
      "id": "source_one",
      "source": "https://github.com/user/rules_repo",
      "authentication": "GH_TOKEN",
      "version": "1.2.1"
    },
    {
      "id": "source_two",
      "source": "rules"
    }
  ],
  "flows": [
    {
      "id": "financedata",
      "description": "finance team flow for discount purposes",
      "input": "data-raw/finance.csv.gz",
      "rules": ["student_discount", "source_two/age_discount"],
      "output": "data/finance.csv"
    }
  ]
}
```

```bash
zendt list
zendt list -s source_one
zendt apply source_one/student_discount -i customers.csv -o customers-out.csv
zendt flow financedata
zendt flow financedata -i other.csv -o other-out.csv
```

`id` cannot contain `/`. `authentication` is an environment-variable name. `version` is a git ref. `description` is for self organization; the command does not print it.

`zendt flow financedata` uses every source in the file, with each source's own token variable and ref. It does not take `-s`, `-v`, or `-a`. The flow can store an input and an output which are overriden by `-i` and `-o` flags if provided for that run.

The same file stem may exist in two sources. The short name works only when it is unique. Otherwise the command refuses and tells you to use `source_id/name`. `list` prints those qualified names. Two files with the same stem inside one source are an error, even in different subfolders.

JSON and YAML files may hold other project keys. zendt reads `sources` and `flows` only. Those keys may also sit under `zendt_config`. Point `config` env variable at that file.

`zendt config --create` and `zendt config --edit` always edit `zendt.json` in the current directory in a interactive way through the terminal. Use that to guide you through creation or editing of the config file. 

## Input and output

Accepted suffixes: `.csv`, `.csv.gz`, `.json`, `.xlsx`.

CSV delimiters are detected from the header and limited to comma and semicolon. The same delimiter is used when the result is written as CSV. JSON input is one object (one row) or an array of objects. `.xlsx` uses openpyxl.

```bash
cat customers.csv | zendt apply student_discount -s ./rules > customers-out.csv
```

A terminal with no `--input` fails instead of waiting for typed rows. An empty pipe fails with `Stdin is empty.` On a terminal, omitting `--output` writes nothing; pass `--printhead` to see the first five rows, or pass `--output` / redirect stdout to get the table. In a pipe, `--printhead` prints the preview on stderr so the CSV on stdout stays intact.

zendt does not validate columns. Enforce the shape in the pipeline (before running zendt rules application) or with an input schema inside the JDM graph.

## How rules are applied

Named rules run in order, each on the original table. New fields are appended. Fields the rule returns that already exist on the input stay as they were. If two rules in one command create the same new column, the command stops. A row the engine rejects stops the command and names the rule and the 1-based row number.

Decision nodes load the called graph from the same source. The key is the file's path relative to the source, without `.json`. Only those graphs are downloaded and compiled.

Below 10,000 rows the command evaluates in the current process, in batches of 20,000. At 10,000 rows or more it uses up to eight processes, and never more than the machine's cores. The full table is still loaded in the parent process.

## Errors

| Exit | When |
| --- | --- |
| 0 | The command finished. |
| 1 | Config, source, authentication, input, missing rule, ambiguous name, invalid graph, or engine failure. The reason is on stderr. |
| 2 | Usage error: unknown flag, missing argument, or `zendt` with no command. |

Common cases: no config and no `--source`; `--version` on a local folder; a rule name that is not in the source; a name that exists in two sources; GitHub 401 or 403; a file that is not a JDM object (`nodes` and `edges`).

## Documentation

The `docs/` directory is the full reference (commands, configuration, rule names, input and output, evaluation, errors). It is a [Zensical](https://zensical.org/) site. From a checkout:

```bash
zensical serve
```

## Development

This repository uses Poetry. The dev group includes pytest.

```bash
poetry install
poetry run pytest
```

The tests live in `tests/` and cover the CLI, config editor, catalog, GitHub listing, input and output, and rule evaluation.
