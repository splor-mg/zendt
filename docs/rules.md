# Rules

A rule file is one JSON graph in the [JDM standard](https://docs.gorules.io/developers/jdm/standard). zendt does not author graphs. Write them in GoRules, then point the command at the files or at the GitHub folder that contains them.

## Names

The name you type in `apply`, in `--find`, and in a flow is the file stem: `student_discount.json` is `student_discount`.

The Zen key is the path of that file relative to the source, without `.json`, using `/` as the separator. In a flat folder the name and the key are the same. In a nested folder they differ.


**Example - Source is pointed at the "rules" folder:**

| file location | Name | Key |
| --- | --- | --- |
| rules/student_discount.json | student_discount | student_discount |
| rules/discounts/student_discount.json | student_discount | discounts/student_discount |


`apply` and flows select a rule by its name (or by `source_id/name`). A decision node inside a graph selects another graph by its key. The `content.key` of a decision node must be that relative path, not a source id.

`list` prints the reference you can paste into a command:

- `student_discount` when the source has no id (you passed a URL or a path).
- `source_one/student_discount` when the source comes from the config and has an id.

## Two sources with the same name

Two different sources might have rules with the same stem (file name). The catalog keeps both. It does not pick a winner.

```text
source_one/student_discount
source_two/student_discount
```

Calling a rule in `apply` or `flow` using only its name is accepted when that stem appears once in the sources currently in use. When it appears more than once, resolution fails and the message names the qualified forms:

```text
student_discount is in source_one and source_two. Use source_one/student_discount.
```

`source_one/student_discount` selects that source. The source id in the prefix must be one of the sources in use. Using `source_two/student_discount` while `--source source_one` is active results in `Rule not found`, because the other source is not being used in the command.

`zendt apply student_discount -s source_one` can use the short name, because that command's catalog contains only `source_one`. `zendt flow` loads every source, so a short name in a flow must be unique across the whole file.

!!! warning

    Inside a source, there can be no duplicate names, including files in different subfolders. The same name is accepted only between different sources. To bypass that, you can set each folder from the same repo or root as different sources, providing them with different ids.

!!! note

    A source id cannot contain `/`. That character separates the id from the rule name.

## Graphs that call other graphs

A decision node calls another graph. zendt collects those calls from nodes whose `type` is `decisionNode`, using `content.key`.

```json
{
  "type": "decisionNode",
  "id": "child",
  "name": "child",
  "content": { "key": "discounts/student_discount" }
}
```

The called graph is loaded from the same source as the caller. Calls are followed until every reached graph has been read. Each graph is read once, including when two parents call it or when two graphs call each other. The loader compiles every loaded graph for that source and gives the engine a loader that returns them by key. The decision node then runs inside the Zen Engine. zendt does not implement the decision node itself.
