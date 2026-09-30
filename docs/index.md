# Zendt

Zendt (Zen Engine for Data Tables) applies [GoRules](https://gorules.io/) business rules to a table from the terminal. The rules are JSON graphs in the [JDM standard](https://docs.gorules.io/developers/jdm/standard). The table is CSV, gzip-compressed CSV, Excel (`.xlsx`), or JSON.

```bash
zendt list -s ./rules
zendt apply student_discount age_discount -s ./rules -i customers.csv -o customers-out.csv
zendt flow financedata
```

The command reads the table, loads only the rules you named (and the decision graphs those rules call), runs them with the [Zen Engine](https://docs.gorules.io/developers/sdks/python), and writes the original columns plus the columns each rule created.

## What a command does

1. Load `.env` from the current directory, without overriding variables that are already set.
2. Resolve where the rules live: a `--source` flag, or `zendt.json`, or the `config` / `sources` environment variables.
3. List the `.json` files in those sources. This step records names and paths. It does not read the graphs yet.
4. For `apply` and `flow`, read the named rules and every decision-node graph they reach.
5. Read the input table.
6. Evaluate each named rule against the original rows and append the new columns.
7. Write the result to a file, or to stdout when stdout is a pipe or a redirect.

`list` stops after step 3 and prints the rule names.

## Where to read next

- [Install](install.md) covers installation steps.
- [Commands](cli.md) is the reference for commands `config`, `list`, `apply`, and `flow`.
- [Configuration](configuration.md) describes the `zendt.json` config file, environment variables, and the interactive editor.
- [Rules](rules.md) describes names, nested files, and graphs that call other graphs.
- [Input and output](input-output.md) describes formats, stdin, stdout, and delimiters.
- [Evaluation](evaluation.md) describes columns, batches, and when extra processes are used.
- [Recommendations](recommendations.md) covers validation, tokens, and large tables.

