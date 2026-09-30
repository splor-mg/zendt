# Configuration

Zendt provides ways for a user to pre-configure rules application without having to rewrite sources and steps every time. 

Instead of always writing a source in `apply` (example: zendt apply rule_example -s https://www.github.com/rules-repo -a TOKEN -v 1.0.1), you can simply store your source and its requirements in a config file and skip calling it when using the command (example: zendt apply rule_example). The same can be done for a set of rules, inputs and outputs that are constantly being used, by using the command `flow` to configure a pipeline.

_OBS: See more about `apply` and `flow` on the [Commands](cli.md) page._


## What can be configured

- `list` and `apply` can take a pre-configured `--source`. 
- `flow` always loads a configuration and depends fully on it. 


The `--source` specification always prevails. When `--source` is omitted, the lookup order is:
1. `zendt.json` in the current directory (default configuration file)
2. `config` or `CONFIG` env variable that stores a path to a JSON or YAML file (which is used as the configuration file).
3. `sources` or `SOURCES`: one source object, or a JSON array of sources. This value is sources only. `flows` or `FLOWS`, when set, is a separate JSON array of flows.
4. Otherwise the command fails.

OBS: The lookup order is relevant. `zendt.json` wins over the environment variables when both are present. `config` wins over `sources`. The lowercase `config` name wins over the uppercase one when both are set. Choose only one way of config to avoid confusion and wrong maintenance.


## How to create `zendt.json`

The interactive commands `zendt config --create` and `zendt config --edit` read and write `zendt.json` in the current directory. Use them to build that file, or write the file yourself. The prompts are described in [Commands](cli.md).


## The Configuration file

A config file is JSON (`.json`) or YAML (`.yaml`, `.yml`). The root value must be one object. Other suffixes are rejected. Invalid JSON or YAML is rejected with the parser message.

Only `sources` and `flows` are read. Any other root key is ignored. If `sources` or `flows` is missing at the root, the same keys are taken from `zendt_config` (use this when you have a large file with other personal configurations). That value may be one object or a list of objects, which are merged. Keys already present at the root are kept.


#### JSON Examples
```json
{
    "sources": [
        {
            "id": "source_one",
            "source": "https://github.com/user/rules_repo.git",
            "authentication": "GH_TOKEN",
            "version": "1.0.0"
        },
        {
            "id": "source_two",
            "source": "home/sample/rules"
        }
    ],
    "flows": [
        {
            "id": "financedata",
            "description": "finance team flow for discount purposes",
            "input": "data-raw/finance.csv.gz",
            "rules": ["student_discount", "age_discount", "other_discount"],
            "output": "data/finance.csv"
        }
    ]
}
```

```json
{
  "other_configs": ["..."],
  "zendt_config": {
      "sources": [
          {
              "id": "source_one",
              "source": "https://github.com/user/rules_repo.git",
              "authentication": "GH_TOKEN",
              "version": "1.0.0"
          },
          {
              "id": "source_two",
              "source": "home/sample/rules"
          }
      ],
      "flows": [
          {
              "id": "financedata",
              "description": "finance team flow for discount purposes",
              "input": "data-raw/finance.csv.gz",
              "rules": ["student_discount", "age_discount", "other_discount"],
              "output": "data/finance.csv"
          }
      ]
  }
}
```

#### YAML Examples
```yaml
name: datapackage
zendt_config:
  - sources:
      - id: reports
        source: https://github.com/user/rules
  - flows:
      - id: receita
        rules: [is_asps_rec]
```

### Sources

`sources` is required. It must be a non-empty array. Each item is an object.

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Name used in `source_id/rule` and in `--source <id>`. Unique. Must not contain `/`. |
| `source` | yes | GitHub URL, or a local directory or file |
| `authentication` | no | Name of the environment variable that holds a GitHub token. Not the token. Remote sources only. |
| `version` | no | Git tag, branch, or other ref. Remote sources only. Omitted means `HEAD`, unless the URL already contains a ref. |

- Paths inside the file are resolved when the file is loaded. A relative `source`, `input`, or `output` is resolved against the directory that contains the config file. A remote URL is left unchanged. Values that arrive through the `sources` environment variable are resolved against the current directory, because there is no file.
  _OBS: Unknown fields on a source are ignored. They are not an error._

- `version`: can be a git tag or ref. The string is sent to the GitHub git trees API as the ref. If the URL is already a `tree` or `blob` URL, its ref is used when `version` is omitted. `zendt apply -v other-ref` replaces the stored version for that run.

- `authentication` names a variable such as `GH_TOKEN`. The command reads `.env` in the current directory and then the process environment. A variable that is already set is not replaced by `.env`. If the named variable is missing, the request is sent without a token. GitHub responds with 401 or 403, and the command exits with `AuthError`. Do not write the token in the config file.


OBS: A local `source` does not use `authentication` or `version`. The editor (`config --edit`) removes those fields when you change a source to a local path. `--version` on a local `--source` is an error.

### Flows

`flows` is optional (the config file can have only source configuration for `apply` command usage, but for `flow` usage, flows must be set in the config file). When present, it must be an array. Each flow is an object.

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Argument to `zendt flow <id>`. Unique. |
| `rules` | yes | Non-empty list of rule names. Each item is a file stem or `source_id/name`. |
| `description` | no | Stored for people reading the file. The command does not print it. |
| `input` | no | Default input path for this flow. Omitted means stdin, unless `-i` is passed. |
| `output` | no | Default output path for this flow. Omitted means the stdout rules, unless `-o` is passed. |

_OBS: Unknown fields on a flow are ignored._

- There is no source field on a flow. `zendt flow financedata` searches every source in the file. A short name has to match exactly one rule in that set. A name that exists in two sources must be written as `source_id/name`. See [Rules](rules.md).

- The `-i` and `-o` flags on the `flow` command replace `input` and `output` configured on `flows` for that specific run. Example: `zendt flow financedata -i data/example.csv`


## Environment variables

Instead of creating `zendt.json`, which is the standard configuration file for zendt, you can try two other alternatives:

1. Using another configuration file that can contain other configurations (which will be ignored by zendt). The path to this file must be provided in a `config` (or `CONFIG`) env variable.
2. Writing config directly in env variables (`sources` and `flows`).

| Variable | Role |
| --- | --- |
| `config`, `CONFIG` | Path to a JSON or YAML config file |
| `sources`, `SOURCES` | One source object, or a JSON array of source objects. No flows. |
| `flows`, `FLOWS` | JSON array of flows. Optional. Omitted means no flows. |
| The name stored in `authentication` or passed with `-a` | The GitHub token |

```bash
export CONFIG=datapackage.yaml
export GH_TOKEN=github_pat_...
zendt flow financedata
```

```bash
export SOURCES='[{"id":"rules","source":"https://github.com/user/rules"}]'
export FLOWS='[{"id":"score","rules":["flag"]}]'
zendt flow score -i customers.csv
```

_OBS: `.env` in the current directory is loaded by `list`, `apply`, and `flow` before sources are resolved._

## What the loader rejects

- Root value is not an object, including a YAML file that is empty or a list.
- `sources` is missing, not an array, or empty.
- A source is not an object, or it lacks `id` or `source`.
- Two sources share an id, or an id contains `/`.
- `flows` is not an array.
- A flow is not an object, lacks `id` or `rules`, or `rules` is empty or not a list.
- Two flows share an id.
- The file type is not `.json`, `.yaml`, or `.yml`.
- The `sources` or `flows` environment variable is not valid JSON.
- `sources` is not one source object or an array of sources.

A missing `zendt.json` is not an error when `config` or `sources` is set. It is an error when nothing is set and the command needed a config.
