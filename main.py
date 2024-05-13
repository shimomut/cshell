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



class CraftShellApp(*Config.plugins, cmd2.Cmd):

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

    argparser = cmd2.Cmd2ArgumentParser(description="Launch FireFox")

    @cmd2.with_category(CATEGORY_CRAFTSHELL)
    @cmd2.with_argparser(argparser)
    def do_firefox(self, args):

        self.poutput(f"Starting FireFox")

        subprocess.run(
            ["c:/Program Files/Mozilla Firefox/firefox.exe"], 
            cwd="c:/Program Files/Mozilla Firefox"
            )


    argparser = cmd2.Cmd2ArgumentParser(description="Search keywords by Google")
    argparser.add_argument("words", metavar="WORDS", nargs="+", help="Keywords to search")

    @cmd2.with_category(CATEGORY_CRAFTSHELL)
    @cmd2.with_argparser(argparser)
    def do_google(self, args):
        query = urllib.parse.quote_plus(" ".join(args.words))
        url = f"https://www.google.com/search?q={query}"
        
        self.poutput(f"Opening {url}")
        
        webbrowser.open(url)        


    argparser = cmd2.Cmd2ArgumentParser(description="Search keywords by Eijiro")
    argparser.add_argument("words", metavar="WORDS", nargs="+", help="Keywords to search")

    @cmd2.with_category(CATEGORY_CRAFTSHELL)
    @cmd2.with_argparser(argparser)
    def do_eijiro(self, args):
        query = urllib.parse.quote_plus(" ".join(args.words))
        url = f"http://eow.alc.co.jp/search?q={query}"
        
        self.poutput(f"Opening {url}")
        
        webbrowser.open(url)        


    argparser = cmd2.Cmd2ArgumentParser(description="Translate EN<->JA by Google Translate")
    argparser.add_argument("words", metavar="WORDS", nargs="+", help="Text to translate")

    @cmd2.with_category(CATEGORY_CRAFTSHELL)
    @cmd2.with_argparser(argparser)
    def do_translate(self, args):

        text = " ".join(args.words)
        
        src_lang = "en"
        for c in text:
            if ord(c) > 255:
                src_lang = "ja"
                break
        
        query = urllib.parse.quote_plus(text)

        if src_lang == "en":
            url = f"https://translate.google.co.jp/#en/ja/{query}"
        elif src_lang == "ja":
            url = f"https://translate.google.co.jp/#ja/en/{query}"

        webbrowser.open(url)        


    argparser = cmd2.Cmd2ArgumentParser(description="Start a screensaver")

    @cmd2.with_category(CATEGORY_CRAFTSHELL)
    @cmd2.with_argparser(argparser)
    def do_screensaver(self, args):

        self.poutput(f"Starting screensaver")
        
        osutils.start_screensaver()


if __name__ == "__main__":
    app = CraftShellApp()
    app.cmdloop()
