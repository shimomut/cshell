import os
import shutil

import cmd2

import misc


# .cshell paths
data_dir = os.path.expanduser("~/.cshell")
history_file_path = os.path.join(data_dir, "history.dat")
config_file_path = os.path.join(data_dir, "config.py")
startup_file_path = os.path.join(data_dir, "startup.csh")


# create config.py if it doesn't exist
os.makedirs(data_dir, exist_ok=True)
if not os.path.exists(config_file_path):
    shutil.copyfile(os.path.join(os.path.dirname(__file__), "_config.py"), config_file_path)

# create startup.csh if it doesn't exist
if not os.path.exists(startup_file_path):
    shutil.copyfile(os.path.join(os.path.dirname(__file__), "_startup.csh"), startup_file_path)

# load config.py
user_config = misc.UserConfig.instance()
user_config.reload(config_file_path)

Config = user_config.get("Config")


class CraftShellApp(*Config.plugins, cmd2.Cmd):

    def __init__(self):

        super().__init__(
            multiline_commands=["echo"],
            persistent_history_file=history_file_path,
            startup_script=startup_file_path, 
            silence_startup_script=True,
            include_ipy=True,
        )

        #self.intro = cmd2.style("Welcome to CraftShell", fg=cmd2.Fg.RED, bg=cmd2.Bg.WHITE, bold=True)
        self.prompt = cmd2.style("▶ ", fg=cmd2.Fg.GREEN, bg=None, bold=False)

        self.register_postcmd_hook(self.on_command_executed)

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Set the default category name
        self.default_category = "cmd2 Built-in Commands"


    # -----
    # Hooks
    
    def on_command_executed(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:
        
        # Save command history immediately
        self._persist_history()

        return data


if __name__ == "__main__":
    app = CraftShellApp()
    app.cmdloop()
