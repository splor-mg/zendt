# Evaluation

!!! note

    The current zendt version supports only rules that generate an object result. Graphs that return a scalar or a list fail.

`apply` and `flow` run each named rule on the original rows. The result is the input table with new columns added on the right, one group of columns per rule, in the order the rules were named.

## What each rule sees

Rule 2 does not see columns created by rule 1. Both rules receive the input table. That is deliberate: the output of one rule is not the input schema of the next. If a later rule needs a column from an earlier rule, that calculation has to live inside one graph, usually through a decision node that calls the other graph. See [Rules](rules.md).

The Zen Engine returns one result object per input row. zendt reads `result` from that object.

- Fields that already exist on the input table are dropped.
- Fields that are new are appended.
- If a rule returns only fields the table already has, it adds no columns. The row count still has to match.
- If a rule adds a column name that an earlier rule in this command already added, the command stops. The original columns of the table are not considered a repeat, because those fields were dropped before this check.

A graph that echoes its input, including a decision node with `passThrough` that copies input fields next to new ones, therefore keeps the original cells and adds only the new names. zendt does not replace the row with the engine's result object.

## Failure of one row

Evaluation is row-oriented. If a row's result is unsuccessful, or has no `data.result` object, the command stops. The message names the rule, the input row number starting at 1, and the engine's error type and source when those fields exist:

```text
Rule 'x' failed on input row 2: NodeError: Failed to evaluate expression: "missing + 1"
```

Rows after the failing batch are not written. There is no partial output file from a failed command: the exception is raised before `write_output`.

The number of result rows must equal the number of input rows.

## Compilation

Graphs are compiled once per source and then reused for every row. In the single-process path, the engine is built again only when the next rule comes from a different source. Child graphs loaded for decision nodes are compiled in that same map, under their Zen keys, and the engine's loader returns them.

A value that is not a map of graphs, or a graph object without `nodes` and `edges`, fails before Zen is called. A graph Zen itself rejects fails.

## One process or several

The `apply` and `flow` commands use parallelism to provide results faster according to the input's size and the computer's processing capacity.

| Rows | Processes |
| --- | --- |
| Fewer than 10,000 | 1, in the current process |
| 10,000 or more | `min(CPU cores, 8)`, and never more processes than rows |

`os.cpu_count()` supplies the core count. If it is unavailable, the parallel path uses one process.

Within a process, rows are sent to `evaluate_batch` in batches of 20,000. The batch is released before the next one is built.

On the parallel path the table is split into about one slice per worker. Each worker then walks its slice in batches of 20,000. Workers are started with `spawn`, so each one imports a fresh interpreter, compiles the rules itself, and does not inherit the parent's engine. Numeric libraries in the worker are pinned to one thread (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`) so the workers do not also multiply threads inside one core.

The parent keeps the full table. It copies each slice to a worker and receives back only the columns that the rule added, in input order. The pool is reused for the next rule when the worker count is the same and the compiled rule map is the same object. A different worker count closes it and starts another. A failure in a worker closes it. The pool is also closed when the process exits.

The parallel path and the single-process path return the same columns. Parallelism does not change rule order or which fields are kept.

## Memory

The input table, the loaded graphs, and the result all live in the command's process. A table that does not fit in RAM fails while being read, before a worker count is chosen. Splitting the work across cores copies slices; it does not remove the parent copy.

This command is built for one machine and one table that pandas can hold. It does not distribute rows across a cluster. For big data, see [Go Rules official recommendations](https://docs.gorules.io/developers/integrations/aws-glue). 
