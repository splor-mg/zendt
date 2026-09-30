# Install

### First Step: Install zendt

Zendt is distributed via [PyPI](https://pypi.org/). To install the package, you can run the following commands in the terminal:

```bash
pip install zendt
zendt -V
```

??? note

    Zendt requires Python 3.13 or newer.

- `zendt -V` prints the installed version, for example `zendt 0.1.0`. The short flag is uppercase `-V`.

    _OBS: Lowercase `-v` (`--version`) is used with `list` and `apply` to reference the git ref of a rules repository._

The package installs a `zendt` command. These two forms call the same application:

```bash
zendt --help
python -m zendt --help
```

## What gets installed

The command depends on the Zen Engine (`zen-engine`), pandas, openpyxl, Typer, requests, PyYAML, python-dotenv, and prompt-toolkit. `pip` installs them with zendt. Excel `.xlsx` files use openpyxl.

## Check that the command can see your rules

From a directory that contains a folder of JDM files:

```bash
zendt list -s ./rules
```

A successful list prints `Rules found in provided sources:` and one name per line. The graphs are not executed by `list`.
