import os

import cmd2

from config import Config


class CraftShellApp(*Config.plugins, cmd2.Cmd):

    def __init__(self):

        self.data_dir = os.path.expanduser("~/.cshell")
        os.makedirs(self.data_dir, exist_ok=True)

        super().__init__(
            multiline_commands=["echo"],
            persistent_history_file= os.path.join(self.data_dir, "history.dat"),
            startup_script="scripts/startup.txt",
            include_ipy=True,
        )

        self.intro = cmd2.style("Welcome to CraftShell", fg=cmd2.Fg.RED, bg=cmd2.Bg.WHITE, bold=True)
        self.prompt = cmd2.style("▶ ", fg=cmd2.Fg.GREEN, bg=None, bold=False)

        self.register_postcmd_hook(self.on_command_executed)

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Set the default category name
        self.default_category = "cmd2 Built-in Commands"


    # -----
    # Hooks
    
    def on_command_executed(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:
        return data


if __name__ == "__main__":
    app = CraftShellApp()
    app.cmdloop()
