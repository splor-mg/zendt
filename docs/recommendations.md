# Recommendations

## Validate the table before the rules run

zendt reads the file and passes each row to the engine. It does not check column names, types, or required fields. A row that does not match what the graph expects fails during evaluation, with the rule name and the row number.

If the rules depend on a shape, enforce it before `apply` or `flow`: in the pipeline that produces the file, or inside the graph. GoRules can reject a bad row before the rest of the graph runs by declaring an input schema on the graph. That check is part of the JDM document, not a zendt flag. The GoRules description of that pattern is [input schema validation](https://docs.gorules.io/learn/authoring/patterns#input-schema-validation).

## Keep tokens out of the config file

`authentication` and `-a` are each the name of an environment variable. Put the token in the environment or in `.env`, which stays out of the rules repository. `.env` does not override a variable that is already set in the process.

## Use a qualified name when stems collide

If two sources both contain `student_discount.json`, write `source_one/student_discount` in the command and in the flow. The command will not choose the first source, the local file, or the newer ref for you.

Give each source an id with no `/`. Use a second source id when you need two refs of the same repository at once.

## Point GitHub at the rules folder

A repository URL lists every JSON file GitHub returns in one tree. A truncated tree fails. Pass the `tree` URL of the folder that contains the rules, and pass `-v` when you need a ref other than the one in the URL or `HEAD`.

## Size the machine for the whole table

The command loads the full table, then optionally splits evaluation across up to eight cores once the table has at least 10,000 rows. The parent process still holds the table. A result that also has to be one CSV on stdout or one file is assembled in that same process.

Use zendt when the table fits in RAM on one machine. A table that does not fit will fail at read time, before evaluation starts.
