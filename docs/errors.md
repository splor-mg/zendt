| Class        | When to raise it                                                                              |
|--------------|-----------------------------------------------------------------------------------------------|
| ZendbError   | Base only. Catch this in the CLI. Do not raise it directly unless nothing more specific fits. |
| ConfigError  | zendb.json missing, invalid JSON, duplicate ids, unknown flow id                              |
| SourceError  | Path/URL/id cannot be resolved, local folder missing, git host/ref failure                    |
| AuthError    | --a / authentication names an env var that is missing or empty                                |
| InputError   | Bad --input/--output, stdin used on a TTY, unsupported format                                 |
| RuleNotFound | --rules name (or a flow rule) not in the source                                               |
| EngineError  | Zen Engine failed on a row/graph                                                              |