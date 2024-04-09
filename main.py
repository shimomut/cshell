import os
import time
import pprint
import subprocess
import webbrowser
import urllib

import cmd2
from cmd2 import Bg, Fg, style

from config import Config
import osutils


class CraftShellApp(cmd2.Cmd):

    CATEGORY_CRAFTSHELL = "CraftShell operations"

    def __init__(self):
        super().__init__(
            multiline_commands=["echo"],
            persistent_history_file="cmd2_history.dat",
            startup_script="scripts/startup.txt",
            include_ipy=True,
        )

        self.intro = style("Welcome to CraftShell", fg=Fg.RED, bg=Bg.WHITE, bold=True)
        self.prompt = style("▶ ", fg=Fg.GREEN, bg=None, bold=False)

        self.register_postcmd_hook(self.on_command_executed)

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Set the default category name
        self.default_category = "cmd2 Built-in Commands"


    # -----
    # Hooks
    def on_command_executed(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:
        return data


    # --------
    # commands

    argparser = cmd2.Cmd2ArgumentParser(description="Create a cluster with JSON file")
    argparser.add_argument("words", metavar="WORDS", nargs="+", help="Keywords to search")

    @cmd2.with_category(CATEGORY_CRAFTSHELL)
    @cmd2.with_argparser(argparser)
    def do_google(self, args):
        query = urllib.parse.quote_plus(" ".join(args.words))
        url = f"https://www.google.com/search?q={query}"
        
        self.poutput(f"Opening {url}")
        
        webbrowser.open(url)        


    argparser = cmd2.Cmd2ArgumentParser(description="Start the screensaver")

    @cmd2.with_category(CATEGORY_CRAFTSHELL)
    @cmd2.with_argparser(argparser)
    def do_screensaver(self, args):
        osutils.start_screensaver()


if __name__ == "__main__":
    app = CraftShellApp()
    app.cmdloop()
