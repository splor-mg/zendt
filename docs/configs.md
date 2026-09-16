## What's the purpose of zendb configuration file?

2 purposes:
1- configure sources to faster reuse
2- configure flows to manage pipelines easily


## How to Create "zendb.json"

You can create the zendb.json file manually by following the instructions in this documentation or you can directly call the `zendb config --create` command to create the file in a interactive way.

1. Call `zendb config --create` or `zendb config --c` in the terminal.
2. The terminal will proceed to ask you all the questions necessary for the file creation.
3. The file will be saved in the root of your project and you can manually edit it or use `zendb config --edit` whenever necessary.

If you only want to create a sample file for manual edit you can use `zendb config -c sample` to import the sample config file to your project.


## How to Edit "zendb.json"

You can edit the zendb.json file manually by following the documentation or you can directly call the `zendb config --edit` command to edit the file (or parts of it) in a interactive way.

.... [to be written]


## Accepted Parameters in Config File

### Sources Configuration

Manage all the repos and directories with rule files that will be used within your project.

- id: unique name that will be used as the source identifier. Can be passed to `zendb apply --source` / `zendb list --source` instead of the full path or URL.
- source: GitHub or GitLab repository URL, or a local directory path.
- authentication: _optional, only for git repos_. Name of the env variable that contains your git token. Not the token itself.
- version: _optional, only for git repos_. Git **tag** or **branch** name. Defaults to the latest tag; if the repo has no tags, the default branch (`main` / `master`).

### Flows Configuration

Manage your rules application pipelines by configuring everything beforehand. Flows are invoked with `zendb flow <id>`, not with `zendb apply`.

Metadata about the flow:
- id: unique name that will be used as the flow identifier (`zendb flow <id>`).
- description: _optional_. Short note for whoever reads the file. Not used by CLI help.

Data used when the flow runs (same meaning as `zendb apply`):
- input: _optional_ input data file path. If omitted, the flow reads stdin.
- rules: list of one or more rules that will be applied to this input. Required.
- output: _optional_. Output file path if you want to save the processed file. If omitted, writes to stdout.

**OBS:** the flow rules will be searched within the sources specified in this file. There must be no source configuration inside the flow configs. Configure sources before creating flows.


### Sample Configuration File

```json
{
    "sources": [
        {
            "id": "source_one",
            "source": "https://github.com/user/rules_repo",
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
            "input": "./data-raw/finance.csv.gz",
            "rules": ["student_discount", "age_discount", "other_discount"],
            "output": "./data/finance.csv"
        }
    ]
}
```


### Using the configurations in the terminal

### Source configs:

The source id can be used as an alias on `apply --source` and `list --source`. Instead of writing the whole path or URL, you can use the id:

`zendb apply --s source_one --r test_rule --i data-raw/example.csv --o data/example-processed.csv`

When you use the id (`--s source_one`) all of that source's settings (authentication, URL, version) are applied.

If `--source` is omitted, `apply` and `list` use every source in `zendb.json`. If the file is missing or invalid, the command errors.

### Flow configs:

A flow packs a full apply into one id:

`zendb flow financedata`

That id must exist in `zendb.json`. It already identifies the rules, the input (or stdin), and the output (or stdout).

`zendb flow` does not take `--rules`, `--source`, or `--input`. To pass those flags, use `zendb apply`.

Attention: flow rules are searched in the sources listed in this file. Configure sources before creating flows.
