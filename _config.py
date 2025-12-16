import plugins.app_open_commands
import plugins.webbrowser_commands
import plugins.clipboard_commands
import plugins.aws_utility_commands
import plugins.hyperpod_commands

class Config:
    plugins = [
        plugins.app_open_commands.AppOpenCommands,
        plugins.webbrowser_commands.WebBrowserCommands,
        plugins.clipboard_commands.ClipboardCommands,
        plugins.aws_utility_commands.AwsUtilityCommands,
        plugins.hyperpod_commands.HyperPodCommands,
    ]


class AwsConfig:
    awscli = ["aws"]

    console_pages = {
        "home": "https://console.aws.amazon.com/console/home",
        "s3": "https://console.aws.amazon.com/s3/home",
        "iam": "https://console.aws.amazon.com/iam/home",
        "cf": "https://console.aws.amazon.com/cloudformation/home",
        "hyperpod": "https://console.aws.amazon.com/sagemaker/home#/cluster-management",
    }

