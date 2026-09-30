# Commands

```text
zendt -V
zendt config --create
zendt config --edit
zendt list -s ./rules
zendt list -s source_one -f discount
zendt apply student_discount -s ./rules -i customers.csv -o customers-out.csv
zendt apply student_discount age_discount -s https://github.com/user/rules/tree/main/rules -a GH_TOKEN -v 1.2.1 -i customers.csv
zendt flow financedata
zendt flow financedata -i customers.csv -o customers-out.csv --printhead
```

## Shared flags

| Flag | Short | Commands | Meaning |
| --- | --- | --- | --- |
| `--source` | `-s` | `list`, `apply` | GitHub URL, local file or directory, or the id of a source in the config |
| `--find` | `-f` | `list` | Keep names that contain this text |
| `--version` | `-v` | `list`, `apply` | Git ref of a remote rules repository |
| `--authentication` | `-a` | `list`, `apply` | Name of the environment variable that holds the token |
| `--input` | `-i` | `apply`, `flow` | Input file. Omitted means stdin |
| `--output` | `-o` | `apply`, `flow` | Output file. Omitted means stdout when it is not a terminal |
| `--printhead` | `-ph` | `apply`, `flow` | Print the first rows of the result |
| `--create` | `-c` | `config` | Create `zendt.json` by answering prompts |
| `--edit` | `-e` | `config` | Edit `zendt.json` by answering prompts |
| `--version` | `-V` | the root command only | Print the zendt version and exit |

- `-v` and `-V` are different flags. `zendt -V` prints the program version. `zendt apply -v 1.2.1 student_discount` selects a git ref.

- `-ph` on `apply` and `flow` is `--printhead`. Help for those commands is `zendt apply --help` and `zendt flow --help`.


## How `--source` is resolved

The flag `--source` is used by `list` and `apply`. `flow` does not take `--source`; it always uses the sources in the config.

When `--source` is omitted, the command looks in this order:

1. `zendt.json` in the current directory. Parent directories are not searched.
2. The `config` environment variable, or `CONFIG` if `config` is unset. The value is a path to a JSON or YAML file.
3. The `sources` environment variable, or `SOURCES`: one source object or a JSON array of sources.
4. If none of those exist, the command fails with `ConfigError`.

When `--source` is present, it is one of:

- A remote URL, meaning it starts with `http://`, `https://`, `git@`, or `ssh://`. It is used as that one source and has no id, so rule names are the file stems. Listing succeeds for GitHub `http` and `https` URLs and for GitHub SSH URLs (`git@github.com:owner/repo.git`, `ssh://git@github.com/owner/repo.git`). A `git@` or `ssh://` URL for another host is stored as remote and then fails, because the catalog only understands GitHub.
- An existing local file or directory. The path is used as that one source. It has no id. A YAML or JSON file that exists on disk is a file of rules, not a config file. Point config files at the `config` environment variable instead.
- Otherwise the text is a source id looked up in the config from the list above. An unknown id is `ConfigError`.

Relative local paths are resolved against the current directory. Paths written inside a config file are resolved against the directory that contains that file.

`--version` is valid only for a git source. Passing it with a local path fails with `SourceError`. On a configured source, `-v` replaces the `version` stored in the file for that invocation. `-a` replaces the environment-variable name stored in `authentication`. The flag value is the variable name, never the token.

Details of the URL forms and of private repositories are in [Rules](rules.md). Config file specifications are in [Configuration](configuration.md).

## `zendt config`

Creates or edits `zendt.json` in the current directory.

```bash
zendt config --create
zendt config --edit
```


### Create

The terminal interactively asks for information regarding sources and flows. At least one source has to be set, while flows are optional.

If `zendt.json` already exists, the terminal asks whether to overwrite it. Answering no leaves the file unchanged.

For each source it asks for an id and a location. A location that starts with `http://`, `https://`, `git@`, or `ssh://` is treated as remote: the terminal asks whether the repository is private and, if so, for the name of the environment variable that holds the token, then whether to store a git ref (version). Omitting the version stores no `version` field. zendt then uses the ref already in the URL, or `HEAD` when the URL has none. A local location stores only `id` and `source`. A source id that is empty, contains `/`, or duplicates an id already entered is not added. The terminal asks for that source again. 

A flow asks for an id, a description, a comma-separated list of rule names, and optional input and output paths. If a flow id is empty or duplicated, or a flow has no rule names, the terminal asks again.

### Edit

The editor loads `zendt.json` from the current directory. A missing file tells you to run `zendt config --create` and changes nothing. Invalid JSON, a missing `sources` array, or a `flows` value that is not an array is reported and the file is left unchanged. A missing `flows` key is treated as an empty list.

The menu is:

1. Sources
2. Flows
3. Save and exit

Sources and flows each have a submenu:

1. Create
2. Delete
3. Edit
4. Back

Create uses the same questions as the --create flag. A source id that is empty or contains `/` is not added. A duplicate source id or flow id is not added. A flow with no rule names is not added.

Delete asks for the id and then asks you to confirm. The last remaining source cannot be deleted, while flows may all be deleted.

Edit asks for the id. Pressing Enter keeps the current value of a field. Typing `-` clears an optional field (`authentication`, `version`, `description`, `input`, `output`). The location of a source cannot be cleared. 

Changing a source to a local path removes `authentication` and `version`. 

A flow must keep at least one rule; an empty rules answer leaves that flow unchanged.

## `zendt list`

```bash
zendt list
zendt list -s ./rules
zendt list -s https://github.com/user/rules/tree/main/rules -a GH_TOKEN -v 1.2.1
zendt list -s source_one -f discount
```

The command prints the rules visible in the selected sources. Each line is the rule reference: `source_id/name` when the source has an id, otherwise the file stem. Copy that line into `apply` or into a flow.

The `--find` flag locates references that contain the text. The match is a substring of the printed reference.
Examples:

- `zendt list -f rules/` will list all the rules that are in the "rules/" source (considering that rules is a valid source_id)
- `zendt list -f finance` will return a list of all rules that contain the word "finance"

`list` does not read or validate the JSON bodies of the rules. It only fetches the source and lists all JSON files (except for zendt.json). For more information about the rules' content, see the [Rules](rules.md) section.

## `zendt apply`

```bash
zendt apply student_discount -s ./rules -i customers.csv -o customers-out.csv
zendt apply student_discount age_discount -s source_one -i customers.csv --printhead
cat customers.csv | zendt apply student_discount -s ./rules > customers-out.csv
```

The words after `apply` are the rule names, one or more. Each name is either a file stem (example: 'name') or `source_id/name`. 

Rules are applied sequentially in the order they are written in the command. Each rule sees the original input columns, not columns created by an earlier rule.

The output table is the input table plus the new columns, in that same order. [Evaluation](evaluation.md) describes what "new" means and what happens when two rules create the same column.

See more about `--input` and `--output` in the [Input and output](input-output.md) section.

On a terminal, the full table is not printed. Pass `--printhead` (or `-ph`) to print the first five rows. In a pipe, `--printhead` prints that preview on stderr so the CSV on stdout stays intact.

## `zendt flow`

```bash
zendt flow financedata
zendt flow financedata -i customers.csv -o customers-out.csv --printhead
```

The command runs the flow with the provided id found in the config. The argument is the flow id, not a rule name.

A flow has no source flag. The command loads every source in the config, using each source's own `authentication` and `version`. `-v` and `-a` are not accepted here. One flow may name rules from different sources. A short rule name must be unique across those sources; otherwise use `source_id/name` in the flow's `rules` list. See [Rules](rules.md).

`--input` replaces the flow's `input` for this run. `--output` replaces the flow's `output`. When the flag and the flow field are both omitted, input is stdin and output follows the stdout rules in [Input and output](input-output.md).

