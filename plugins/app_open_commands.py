import subprocess

import cmd2

from .aws_misc import *


class AppOpenCommands:

    CATEGORY = "Application opening commands"


    # ----------
    # completers

    def choices_ssh_hostnames(self, arg_tokens):

        choices = []

        ssh_config_path = os.path.expanduser("~/.ssh/config")
        if os.path.exists(ssh_config_path):
            with open(ssh_config_path) as fd:
                for line in fd:
                    re_result = re.match( r"Host\s([^*]+)$", line.strip() )
                    if re_result:
                        hostname = re_result.group(1)
                        choices.append(hostname)

        return choices


    # --------
    # commands

    argparser = cmd2.Cmd2ArgumentParser(description="Open commands")
    subparsers1 = argparser.add_subparsers(title="sub-commands")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_open(self, args):
        func = getattr(args, "func", None)
        if func is not None:
            func(self, args)
        else:
            self.do_help("open")


    # ----------------
    # commands - vscode

    argparser = subparsers1.add_parser("vscode", help="Open Visual Studio Code")
    argparser.add_argument("--remote", action="store", choices_provider=choices_ssh_hostnames, help="Host name to connect")
    argparser.add_argument("path", metavar="PATH", nargs="*", completer=cmd2.Cmd.path_complete, help="Path to open")

    def _do_vscode(self, args):

        remote_args = []
        if args.remote:
            remote_args = [ "--remote", f"ssh-remote+{args.remote}" ]

        path_args = []
        for path in args.path:
            path_args.append(os.path.expanduser(path))

        cmd = ["code", *remote_args, *path_args]
        subprocess.run(cmd)

    argparser.set_defaults(func=_do_vscode)


    # ----------------
    # commands - ssh

    argparser = cmd2.Cmd2ArgumentParser(description="SSH to remote host")
    argparser.add_argument("host", metavar="HOST", action="store", choices_provider=choices_ssh_hostnames, help="Host name to connect")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_ssh(self, args):

        cmd = [ "ssh", args.host ]
        subprocess.run(cmd)




