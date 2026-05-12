# CraftShell

A cmd2-based command-line framework for utility commands (AWS operations, app launching, clipboard utilities) with a plugin architecture.

## Quick Start

```bash
pip install cmd2 boto3 pexpect
python3 main.py
```

## Architecture

- **Plugin system**: Plugins live in `plugins/`, each is a class mixed into `CraftShellApp` via multiple inheritance
- **Registration**: Plugins are listed in `_config.py` under `Config.plugins`
- **User config**: Stored in `~/.cshell/` (config.py, startup.csh, history.dat)

## Adding Commands

Commands use cmd2 decorators. Each plugin class needs a `CATEGORY` class variable:

```python
class MyCommands:
    CATEGORY = "My Category"

    argparser = cmd2.Cmd2ArgumentParser(description="...")
    argparser.add_argument("name", help="...")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_mycommand(self, args):
        self.poutput("output")
```

For subcommands, use `argparser.add_subparsers()` with `set_defaults(func=handler)`.

## Conventions

- Command methods: `do_commandname`
- Subcommand helpers: `_do_subcommandname`
- Output: use `self.poutput()` not `print()`
- File paths: expand with `os.path.expanduser()`
- External commands: `subprocess.run()`
- AWS CLI path is configurable via `AwsConfig.awscli`

## File Layout

```
main.py              # Entry point
misc.py              # UserConfig utility
_config.py           # Default config template
_startup.csh         # Default startup script template
plugins/
  __init__.py
  app_open_commands.py
  aws_utility_commands.py
  clipboard_commands.py
  hyperpod_commands.py
  hyperpod_misc.py
  aws_misc.py
  webbrowser_commands.py
```

## Adding a New Plugin

1. Create `plugins/my_commands.py` with a class defining `CATEGORY`
2. Import it in `_config.py`
3. Add the class to `Config.plugins`

## Notes

- Internal/private plugins (`*internal*.py`, `*private*.py`) are gitignored
- The app supports IPython embedding (`include_ipy=True`)
