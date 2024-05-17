import time
import datetime
import decimal
import fnmatch

import cmd2
import boto3

from .aws_misc import *


class AwsUtilityCommands:

    CATEGORY = "AWS utility commands"


    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.register_postcmd_hook(self.on_awsut_command_executed)

        self.cached_ec2_instance_name_choices = []
        self.cached_log_group_name_choices = []
        self.cached_log_stream_name_choices = {}


    # -----
    # Hooks
    
    def on_awsut_command_executed(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:

        # Clean completer cache after each command execution
        self.cached_ec2_instance_name_choices = []
        self.cached_log_group_name_choices = []
        self.cached_log_stream_name_choices = {}

        return data


    # -------------
    # boto3 clients

    _ce_client = None
    @staticmethod
    def get_ce_client():
        if not AwsUtilityCommands._ce_client:
            AwsUtilityCommands._ce_client = boto3.client("ce")
        return AwsUtilityCommands._ce_client


    _ec2_client = None
    @staticmethod
    def get_ec2_client():
        if not AwsUtilityCommands._ec2_client:
            AwsUtilityCommands._ec2_client = boto3.client("ec2")
        return AwsUtilityCommands._ec2_client


    _logs_client = None
    @staticmethod
    def get_logs_client():
        if not AwsUtilityCommands._logs_client:
            AwsUtilityCommands._logs_client = boto3.client("logs")
        return AwsUtilityCommands._logs_client


    # ----------
    # completers

    def choices_aws_profiles(self, arg_tokens):

        choices = []

        aws_config_path = os.path.expanduser("~/.aws/config")
        if os.path.exists(aws_config_path):
            with open(aws_config_path) as fd:
                for line in fd:
                    re_result = re.match( r"\[profile\s(.+)\]", line.strip() )
                    if re_result:
                        profile = re_result.group(1)
                        choices.append(profile)

        choices.append("default")

        return choices


    def choices_ec2_instance_names(self, arg_tokens):

        if self.cached_ec2_instance_name_choices:
            return self.cached_ec2_instance_name_choices

        ec2_client = self.get_ec2_client()
        response = ec2_client.describe_instances()
        
        for reservations in response["Reservations"]:
            for instance in reservations["Instances"]:

                name = ""
                for tag in instance["Tags"]:
                    if tag["Key"]=="Name":
                        name = tag["Value"]
                        break

                if name:
                    self.cached_cluster_name_choices.append(name)

        return self.cached_cluster_name_choices


    def choices_log_group_names(self, arg_tokens):

        if self.cached_log_group_name_choices:
            return self.cached_log_group_name_choices

        for log_group in self._list_log_groups_all(""):
            self.cached_log_group_name_choices.append(log_group["logGroupName"])

        return self.cached_log_group_name_choices


    def choices_log_stream_names(self, arg_tokens):

        group_name = None
        group_names = arg_tokens["group_name"]
        if len(group_names)==1:
            group_name = group_names[0]

        if group_name:
            if group_name in self.cached_log_stream_name_choices:
                return self.cached_log_stream_name_choices[group_name]

        self.cached_log_stream_name_choices[group_name] = []

        logs_client = self.get_logs_client()
        response = logs_client.describe_log_streams(logGroupName = group_name)
        for stream in response["logStreams"]:
            self.cached_log_stream_name_choices[group_name].append(stream["logStreamName"])

        return self.cached_log_stream_name_choices[group_name]


    # --------
    # commands

    argparser = cmd2.Cmd2ArgumentParser(description="AWS commands")
    subparsers1 = argparser.add_subparsers(title="sub-commands")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_awsut(self, args):
        func = getattr(args, "func", None)
        if func is not None:
            func(self, args)
        else:
            self.do_help("awsut")


    # ------------------
    # commands - profile

    argparser = subparsers1.add_parser("profile", help="Switch AWS profile")
    argparser.add_argument("profile_name", metavar="PROFILE_NAME", action="store", choices_provider=choices_aws_profiles, help="Name of profile")

    def _do_profile(self, args):
        self.poutput( f"Switching AWS profile to {args.profile_name}" )
        os.environ["AWS_PROFILE"] = args.profile_name

    argparser.set_defaults(func=_do_profile)


    # ----------------
    # commands - costs

    argparser = subparsers1.add_parser("recent-cost", help="Show recent cost")
    argparser.add_argument('--days', action='store', type=int, default=14, help='Number of days to show')

    def _do_recent_cost(self, args):

        client = self.get_ce_client()

        today = datetime.datetime.now().date()
        period_end = today + datetime.timedelta( days=1 )
        period_start = period_end - datetime.timedelta( days=args.days )
        
        params = {
            "TimePeriod" : { 
                "Start" : period_start.strftime("%Y-%m-%d"), 
                "End" : period_end.strftime("%Y-%m-%d") 
            },
            "Granularity" : "DAILY",
            "Metrics" : [ 
                "AmortizedCost", 
                #"BlendedCost", 
                #"NetAmortizedCost", 
                #"NetUnblendedCost", 
                #"NormalizedUsageAmount", 
                #"UnblendedCost", 
                #"UsageQuantity",
            ]
        }
        
        response = client.get_cost_and_usage( **params )
        
        for item in response["ResultsByTime"]:
            start = item["TimePeriod"]["Start"]
            amount = decimal.Decimal(item["Total"]["AmortizedCost"]["Amount"])
            unit = item["Total"]["AmortizedCost"]["Unit"]
            self.poutput( f"  {start} : {amount:6.2f} {unit}" )

    argparser.set_defaults(func=_do_recent_cost)


    # ----------------
    # commands - ec2

    argparser = subparsers1.add_parser("ec2", help="EC2 commands")
    subparsers2 = argparser.add_subparsers(title="sub-commands")


    # ---

    argparser = subparsers2.add_parser('list', help='List EC2 instances with status')

    def _do_ec2_list(self, args):

        ec2_client = self.get_ec2_client()

        response = ec2_client.describe_instances()
        
        print( "Existing instances:" )

        for reservations in response["Reservations"]:
            for instance in reservations["Instances"]:

                instance_id = instance["InstanceId"]
                
                name = ""
                for tag in instance["Tags"]:
                    if tag["Key"]=="Name":
                        name = tag["Value"]
                        break

                state = instance["State"]["Name"]
                
                public_dns_name = ""
                for network_interface in instance["NetworkInterfaces"]:
                    #pprint.pprint(network_interface)
                    if "Association" in network_interface:
                        public_dns_name = network_interface["Association"]["PublicDnsName"]
                        break

                print( "  {:>20} : {:<19} : {:<8} : {}".format( name, instance_id, state, public_dns_name ) )

    argparser.set_defaults(func=_do_ec2_list)


    # ---

    def _ec2_instance_match(self, instance, name):

        for tag in instance["Tags"]:
            if tag["Key"]=="Name":
                if tag["Value"]==name:
                    return True

        return False


    # ---

    argparser = subparsers2.add_parser('start', help='Start instance by name')
    argparser.add_argument("instance_name", metavar="INSTANCE_NAME", action="store", choices_provider=choices_ec2_instance_names, help="Name of instance")

    def _do_ec2_start(self, args):

        ec2_client = self.get_ec2_client()
        response = ec2_client.describe_instances()
        
        def _start(instance):
            response = ec2_client.start_instances( InstanceIds = [ instance["InstanceId"] ] )
            
        for reservations in response["Reservations"]:
            for instance in reservations["Instances"]:
                if self._ec2_instance_match( instance, args.instance_name ):
                    _start(instance)
                    return
                        
        print( f"Error : EC2 instance [{args.instance_name}] not found." )

    argparser.set_defaults(func=_do_ec2_start)


    # ---

    argparser = subparsers2.add_parser('stop', help='Stop instance by name')
    argparser.add_argument("instance_name", metavar="INSTANCE_NAME", action="store", choices_provider=choices_ec2_instance_names, help="Name of instance")

    def _do_ec2_stop(self, args):

        ec2_client = self.get_ec2_client()
        response = ec2_client.describe_instances()
        
        def _stop(instance):
            response = ec2_client.stop_instances( InstanceIds = [ instance["InstanceId"] ] )
            
        for reservations in response["Reservations"]:
            for instance in reservations["Instances"]:
                if self._ec2_instance_match( instance, args.instance_name ):
                    _stop(instance)
                    return
                        
        print( f"Error : EC2 instance [{args.instance_name}] not found." )

    argparser.set_defaults(func=_do_ec2_stop)


    # ---

    argparser = subparsers2.add_parser('reboot', help='Reboot instance by name')
    argparser.add_argument("instance_name", metavar="INSTANCE_NAME", action="store", choices_provider=choices_ec2_instance_names, help="Name of instance")

    def _do_ec2_reboot(self, args):

        ec2_client = self.get_ec2_client()
        response = ec2_client.describe_instances()
        
        def _reboot(instance):
            response = ec2_client.reboot_instances( InstanceIds = [ instance["InstanceId"] ] )
            
        for reservations in response["Reservations"]:
            for instance in reservations["Instances"]:
                if self._ec2_instance_match( instance, args.instance_name ):
                    _reboot(instance)
                    return
                        
        print( f"Error : EC2 instance [{args.instance_name}] not found." )

    argparser.set_defaults(func=_do_ec2_reboot)


    # ----------------
    # commands - logs

    argparser = subparsers1.add_parser("logs", help="Logs commands")
    subparsers2 = argparser.add_subparsers(title="sub-commands")


    # ---

    def _list_log_groups_all(self, prefix):

        logs_client = self.get_logs_client()

        log_groups = []
        next_tolen = None

        while True:

            params = {
                "limit" : 50,
            }

            if prefix:
                params["logGroupNamePrefix"] = prefix

            if next_tolen:
                params["nextToken"] = next_tolen

            response = logs_client.describe_log_groups(**params)

            log_groups += response["logGroups"]

            if "nextToken" in response:
                next_tolen = response["nextToken"]
            else:
                break
        
        return log_groups


    # ---

    argparser = subparsers2.add_parser('list', help='List log groups')
    argparser.add_argument("group_name", metavar="GROUP_NAME", nargs="?", help="Log group name pattern with widecards")

    def _do_logs_list(self, args):

        logs_client = self.get_logs_client()

        if args.group_name is None:
            args.group_name = "*"

        prefix = args.group_name
        pos = prefix.find("*")
        if pos>=0:
            prefix = prefix[:pos]
        pos = prefix.find("?")
        if pos>=0:
            prefix = prefix[:pos]

        last_found_log_group = None
        num_found = 0

        print("Log groups:")
        for log_group in self._list_log_groups_all(prefix):
            if fnmatch.fnmatch( log_group["logGroupName"], args.group_name ):
                print( "  " + log_group["logGroupName"] )
                last_found_log_group = log_group
                num_found += 1

        if num_found==1:
            print("")
            print("Streams:")
            response = logs_client.describe_log_streams( logGroupName = last_found_log_group["logGroupName"] )
            for stream in response["logStreams"]:
                print( "  " + stream["logStreamName"] )

    argparser.set_defaults(func=_do_logs_list)


    # ---

    argparser = subparsers2.add_parser('monitor', help='Monitor a log stream')
    argparser.add_argument("group_name", metavar="GROUP_NAME", choices_provider=choices_log_group_names, help="Log group name")
    argparser.add_argument("stream_name", metavar="STREAM_NAME", choices_provider=choices_log_stream_names, help="Log stream name to monitor")
    argparser.add_argument('--freq', action='store', type=int, default=5, help='Polling frequency in seconds')
    argparser.add_argument('--lookback', action='store', type=int, default=60, help='Lookback window in minutes')

    def _do_logs_monitor(self, args):

        logs_client = self.get_logs_client()

        start_time = int( ( time.time() - args.lookback * 60 ) * 1000 )

        def _monitor():

            nextToken = None
            while True:

                params = {
                    "logGroupName" : args.group_name,
                    "logStreamName" : args.stream_name,
                    "startFromHead" : True,
                    "limit" : 1000,
                }

                if nextToken:
                    params["nextToken"] = nextToken
                else:
                    params["startTime"] = start_time

                try:
                    response = logs_client.get_log_events( **params )
                except logs_client.exceptions.ResourceNotFoundException as e:
                    print( "Log group or stream not found [ %s, %s ]" % (args.log_group, args.stream) )
                    return

                for event in response["events"]:

                    if start_time > event["timestamp"]:
                        continue

                    message = event["message"]
                    message = message.replace( "\0", "\\0" )
                    print( message )

                assert "nextForwardToken" in response, "nextForwardToken not found"

                if response["nextForwardToken"] != nextToken:
                    nextToken = response["nextForwardToken"]
                else:
                    time.sleep(args.freq)

        try:
            _monitor()
        except KeyboardInterrupt:
            pass

    argparser.set_defaults(func=_do_logs_monitor)


    # ---

    argparser = subparsers2.add_parser('export', help='Export a log group in a Zip file')
    argparser.add_argument("group_name", metavar="GROUP_NAME", help="Log group name to export")
    argparser.add_argument("s3_path", metavar="S3_PATH", help="S3 path as a working place")
    argparser.add_argument('--start-datetime', action='store', required=True, help='Start date-time in UTC, in YYYYMMDD_HHMMSS format')
    argparser.add_argument('--end-datetime', action='store', required=True, help='End date-time in UTC, in YYYYMMDD_HHMMSS format')

    def _do_logs_export(self, args):

        exporter = LogsExporter(
            logs_client=self.get_logs_client(),
            log_group=args.group_name, 
            s3_path=args.s3_path, 
            start_datetime=args.start_datetime, 
            end_datetime=args.end_datetime )
        exporter.run()

    argparser.set_defaults(func=_do_logs_export)

