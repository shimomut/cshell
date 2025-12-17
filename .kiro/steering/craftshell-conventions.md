---
inclusion: always
---

# CraftShell Project Conventions

## Project Overview

CraftShell is a cmd2-based command-line framework for utility commands, with a focus on AWS operations, application launching, and clipboard utilities. The project uses a plugin architecture where commands are organized into modular plugin classes.

## Architecture Patterns

### Plugin System

- All plugins are located in the `plugins/` directory
- Each plugin is a Python class that gets mixed into the main `CraftShellApp` class via multiple inheritance
- Plugins are registered in `_config.py` under the `Config.plugins` list
- Plugin classes should define a `CATEGORY` class variable for command grouping

### Command Structure

Commands follow the cmd2 framework patterns:

```python
class MyCommands:
    CATEGORY = "My Command Category"
    
    argparser = cmd2.Cmd2ArgumentParser(description="Command description")
    # Add arguments to argparser
    
    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_commandname(self, args):
        # Command implementation
        pass
```

### Subcommands Pattern

For commands with subcommands (like `open vscode`, `open ssh`):

```python
argparser = cmd2.Cmd2ArgumentParser(description="Parent command")
subparsers = argparser.add_subparsers(title="sub-commands")

@cmd2.with_category(CATEGORY)
@cmd2.with_argparser(argparser)
def do_parent(self, args):
    func = getattr(args, "func", None)
    if func is not None:
        func(self, args)
    else:
        self.do_help("parent")

# Define subcommand
subparser = subparsers.add_parser("subcommand", help="Help text")
# Add arguments to subparser

def _do_subcommand(self, args):
    # Implementation
    pass

subparser.set_defaults(func=_do_subcommand)
```

## Configuration Management

### User Configuration

- User config is stored in `~/.cshell/` directory
- `config.py` - Plugin configuration (copied from `_config.py` on first run)
- `startup.csh` - Startup script (copied from `_startup.csh` on first run)
- `history.dat` - Command history persistence

### Config Classes

- `Config` class in `_config.py` defines which plugins to load
- `AwsConfig` class defines AWS-specific settings like console URLs and CLI paths
- User can customize these by editing `~/.cshell/config.py`

## Code Style and Conventions

### Import Organization

1. Standard library imports
2. Third-party imports (cmd2, boto3, pexpect)
3. Local imports (misc, plugins)

Example:
```python
import os
import time

import cmd2
import boto3

import misc
from .aws_misc import *
```

### Naming Conventions

- Command methods: `do_commandname` (lowercase with underscores)
- Helper methods for subcommands: `_do_subcommandname` (prefix with underscore)
- Completer methods: `choices_description` (e.g., `choices_ssh_hostnames`)
- Plugin classes: `PascalCase` ending with `Commands` (e.g., `ClipboardCommands`)

### Command Categories

Use descriptive category names:
- "Application opening commands"
- "Clipboard commands"
- "AWS utility commands"
- "HyperPod commands"
- "Web browser commands"

## AWS Integration

### AWS CLI Execution

- AWS CLI path is configurable via `AwsConfig.awscli`
- Default: `["aws"]`
- Can be customized for different environments

### AWS Console URLs

- Console page URLs are defined in `AwsConfig.console_pages`
- Use descriptive keys: "home", "s3", "iam", "cf", "hyperpod"

### Boto3 Usage

- Import boto3 in plugins that need AWS SDK access
- Use for programmatic AWS operations beyond CLI capabilities

## Dependencies

Required packages (install via pip):
- `cmd2` - Command-line framework
- `boto3` - AWS SDK for Python
- `pexpect` - For interactive command execution

## File Organization

```
.
├── main.py                 # Entry point, app initialization
├── misc.py                 # Utility classes (UserConfig)
├── _config.py              # Default configuration template
├── _startup.csh            # Default startup script template
├── plugins/
│   ├── __init__.py
│   ├── app_open_commands.py
│   ├── aws_misc.py         # AWS utility functions
│   ├── aws_utility_commands.py
│   ├── clipboard_commands.py
│   ├── hyperpod_commands.py
│   ├── hyperpod_misc.py
│   └── webbrowser_commands.py
└── .cshell/                # User config directory (in home)
    ├── config.py
    ├── startup.csh
    └── history.dat
```

## Adding New Plugins

1. Create new file in `plugins/` directory
2. Define plugin class with `CATEGORY` attribute
3. Implement commands using cmd2 decorators
4. Import plugin in `_config.py`
5. Add to `Config.plugins` list

## Best Practices

- Use `cmd2.Cmd2ArgumentParser` for argument parsing
- Provide helpful descriptions for commands and arguments
- Use `@cmd2.with_category()` to organize commands
- Implement custom completers for better UX (e.g., `choices_provider`)
- Use `self.poutput()` for command output (not print)
- Expand user paths with `os.path.expanduser()` when dealing with file paths
- Use `subprocess.run()` for external command execution
