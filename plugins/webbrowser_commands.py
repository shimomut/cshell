import webbrowser
import urllib

import cmd2


class WebBrowserCommands:

    CATEGORY = "Web browser commands"

    argparser = cmd2.Cmd2ArgumentParser(description="Search keywords by Google")
    argparser.add_argument("words", metavar="WORDS", nargs="+", help="Keywords to search")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_google(self, args):
        query = urllib.parse.quote_plus(" ".join(args.words))
        url = f"https://www.google.com/search?q={query}"
        
        self.poutput(f"Opening {url}")
        
        webbrowser.open(url)        


    argparser = cmd2.Cmd2ArgumentParser(description="Search keywords by Eijiro")
    argparser.add_argument("words", metavar="WORDS", nargs="+", help="Keywords to search")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_eijiro(self, args):
        query = urllib.parse.quote_plus(" ".join(args.words))
        url = f"http://eow.alc.co.jp/search?q={query}"
        
        self.poutput(f"Opening {url}")
        
        webbrowser.open(url)        


    argparser = cmd2.Cmd2ArgumentParser(description="Translate EN<->JA by Google Translate")
    argparser.add_argument("words", metavar="WORDS", nargs="+", help="Text to translate")

    @cmd2.with_category(CATEGORY)
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

