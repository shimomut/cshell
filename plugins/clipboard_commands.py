import datetime

import cmd2


class ClipboardCommands:

    CATEGORY = "Clipboard commands"


    argparser = cmd2.Cmd2ArgumentParser(description="Print date and time in various format")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_now(self, args):

        datetime_formats = [
            ( "YYYY/MM/DD HH:MM:SS",   "%Y/%m/%d %H:%M:%S" ),
            ( "YYYY/MM/DD",            "%Y/%m/%d" ),
            ( "YYYYMMDD_HHMMSS",       "%Y%m%d_%H%M%S" ),
            ( "YYYYMMDD",              "%Y%m%d" ),
            ( "YYYY-MM-DD_HH-MM-SS",   "%Y-%m-%d_%H-%M-%S" ),
            ( "YYYY-MM-DD",            "%Y-%m-%d" ),
        ]

        for fmt1, fmt2 in datetime_formats:
            self.poutput( datetime.datetime.now().strftime(fmt2) )

