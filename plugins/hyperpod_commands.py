import os
import time
import json
import pprint
import subprocess
import signal

import pexpect
import pexpect.popen_spawn
import cmd2
from cmd2 import Bg, Fg, style
import boto3

import misc

from .hyperpod_misc import *


# TODO:
# - Make ssh config template configurable
# - parallelize ssh key installation


# FIXME : use poutput() instead of print()
def print_log(logs_client, log_group, stream):

    # FIXME : should use cluster creation time
    start_time = int( ( time.time() - 24 * 60 * 60 ) * 1000 )

    next_token = None
    while True:

        params = {
            "logGroupName" : log_group,
            "logStreamName" : stream,
            "startFromHead" : True,
            "limit" : 1000,
        }

        if next_token:
            params["nextToken"] = next_token
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

        if response["nextForwardToken"] != next_token:
            next_token = response["nextForwardToken"]
        else:
            break





class HyperPodCommands:

    CATEGORY = "HyperPod operations"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        user_config = misc.UserConfig.instance()
        self.aws_config = user_config.get("AwsConfig")
        self.hyperpod_config = user_config.get("HyperPodConfig")

        self.register_postcmd_hook(self.on_hyperpod_command_executed)

        self.cached_cluster_name_choices = []
        self.cached_node_id_choices = {}


    # -----
    # Hooks
    
    def on_hyperpod_command_executed(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:

        # Clean completer cache after each command execution
        self.cached_cluster_name_choices = []
        self.cached_node_id_choices = {}

        return data


    # -------------
    # boto3 clients

    _sagemaker_client = None
    @staticmethod
    def get_sagemaker_client():
        if not HyperPodCommands._sagemaker_client:
            HyperPodCommands._sagemaker_client = boto3.client("sagemaker")
        return HyperPodCommands._sagemaker_client

    _logs_client = None
    @staticmethod
    def get_logs_client():
        if not HyperPodCommands._logs_client:
            HyperPodCommands._logs_client = boto3.client("logs")
        return HyperPodCommands._logs_client


    # ----------
    # completers

    def choices_cluster_names(self, arg_tokens):

        if self.cached_cluster_name_choices:
            return self.cached_cluster_name_choices

        sagemaker_client = self.get_sagemaker_client()
        clusters = list_clusters_all(sagemaker_client)
        for cluster in clusters:
            self.cached_cluster_name_choices.append( cluster["ClusterName"] )

        return self.cached_cluster_name_choices


    def choices_node_ids(self, arg_tokens):

        cluster_name = None
        cluster_names = arg_tokens["cluster_name"]
        if len(cluster_names)==1:
            cluster_name = cluster_names[0]

        if cluster_name in self.cached_node_id_choices:
            return self.cached_node_id_choices[cluster_name]

        self.cached_node_id_choices[cluster_name] = []
        choices = self.cached_node_id_choices[cluster_name]

        sagemaker_client = self.get_sagemaker_client()
        logs_client = self.get_logs_client()

        try:
            cluster = sagemaker_client.describe_cluster(
                ClusterName = cluster_name
            )
        except sagemaker_client.exceptions.ResourceNotFound:
            raise cmd2.CompletionError(f"Cluster [{cluster_name}] not found.")
        
        try:
            nodes = list_cluster_nodes_all( sagemaker_client, cluster_name )
        except sagemaker_client.exceptions.ResourceNotFound:
            raise cmd2.CompletionError(f"Cluster [{cluster_name}] not found.")
        
        hostnames = Hostnames.instance()
        hostnames.resolve(cluster, nodes)
        
        # add choice from existing nodes
        for node in nodes:
            node_id = node["InstanceId"]
            instance_group_name = node["InstanceGroupName"]
            choices.append(node_id)
            hostname = hostnames.get_hostname(node_id)
            if hostname:
                choices.append(hostname)
            choices.append( instance_group_name + "/" + node_id )

        cluster_id = cluster["ClusterArn"].split("/")[-1]
        log_group = f"/aws/sagemaker/Clusters/{cluster_name}/{cluster_id}"

        try:
            streams = list_log_streams_all(logs_client, log_group)
        except logs_client.exceptions.ResourceNotFoundException:
            raise cmd2.CompletionError(f"Log group [{log_group}] not found.")

        # add choice from log stream names
        for stream in streams:
            stream_name = stream["logStreamName"]
            instance_group_name = stream_name.split("/")[-2]
            node_id = stream_name.split("/")[-1]
            choices.append(node_id)
            choices.append( instance_group_name + "/" + node_id )

        return choices


    # --------
    # commands

    argparser = cmd2.Cmd2ArgumentParser(description="HyperPod commands")
    subparsers1 = argparser.add_subparsers(title="sub-commands")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def do_hyperpod(self, args):
        func = getattr(args, "func", None)
        if func is not None:
            func(self, args)
        else:
            self.do_help("hyperpod")


    # ---

    argparser = subparsers1.add_parser("create", help="Create a cluster with JSON file")
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", help="Name of cluster")
    argparser.add_argument("--instances", action="store", required=True, completer=cmd2.Cmd.path_complete, help="JSON formatted config file path for instance groups")
    argparser.add_argument("--vpc", action="store", required=False, completer=cmd2.Cmd.path_complete, help="JSON formatted config file path for VPC")

    def _do_create(self, args):

        params = {
            "ClusterName" : args.cluster_name,
        }

        with open(os.path.expanduser(args.instances)) as fd:
            params["InstanceGroups"] = json.loads(fd.read())

        if args.vpc:
            with open(os.path.expanduser(args.vpc)) as fd:
                params["VpcConfig"] = json.loads(fd.read())

        sagemaker_client = self.get_sagemaker_client()
        response = sagemaker_client.create_cluster(**params)

        cluster_arn = response["ClusterArn"]
        self.poutput(f"Creation started : {cluster_arn}")

    argparser.set_defaults(func=_do_create)


    # ---

    argparser = subparsers1.add_parser("delete", help="Delete a cluster")
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", choices_provider=choices_cluster_names, help="Name of cluster")
    argparser.add_argument("-y", "--yes", action="store_true", default=False, help="Skip confirmation")

    def _do_delete(self, args):

        if not args.yes:
            answer = input(f"Are you sure deleting the cluster [{args.cluster_name}]? [y/N] : ")
            if answer.lower() not in ["y","yes"]:
                return

        sagemaker_client = self.get_sagemaker_client()

        try:
            response = sagemaker_client.delete_cluster(
                ClusterName = args.cluster_name,
            )
        except sagemaker_client.exceptions.ResourceNotFound:
            self.poutput(f"Cluster [{args.cluster_name}] not found.")
            return

        cluster_arn = response["ClusterArn"]
        self.poutput(f"Deletion started : {cluster_arn}")

    argparser.set_defaults(func=_do_delete)


    # ---

    argparser = subparsers1.add_parser("list", help="List clusters in human readable format")
    argparser.add_argument("--details", action="store_true", default=False, help="Show details" )

    def _do_list(self, args):

        sagemaker_client = self.get_sagemaker_client()

        clusters = list_clusters_all(sagemaker_client)

        format_string = "{:<%d} : {:<%d} : {} : {}" % (get_max_len(clusters,"ClusterName"), get_max_len(clusters,"ClusterStatus"))

        for cluster in clusters:

            self.poutput( format_string.format( cluster["ClusterName"], cluster["ClusterStatus"], cluster["CreationTime"].strftime("%Y/%m/%d %H:%M:%S"), cluster["ClusterArn"] ) )

            if cluster["ClusterStatus"] in ["Failed", "RollingBack"]:

                cluster_details = sagemaker_client.describe_cluster(
                    ClusterName = cluster["ClusterName"]
                )

                self.poutput("")
                for line in cluster_details["FailureMessage"].splitlines():
                    self.poutput(f"{line}")
                self.poutput("")
                self.poutput("---")

    argparser.set_defaults(func=_do_list)


    # ---

    argparser = subparsers1.add_parser("describe", help="Describe cluster and its nodes in depth")
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", choices_provider=choices_cluster_names, help="Name of cluster")
    argparser.add_argument("--details", action="store_true", default=False, help="Show details" )

    def _do_describe(self, args):

        sagemaker_client = self.get_sagemaker_client()

        try:
            cluster = sagemaker_client.describe_cluster(
                ClusterName = args.cluster_name
            )
        except sagemaker_client.exceptions.ResourceNotFound:
            self.poutput(f"Cluster [{args.cluster_name}] not found.")
            return
        
        cluster_id = cluster["ClusterArn"].split("/")[-1]
        nodes = list_cluster_nodes_all( sagemaker_client, args.cluster_name )

        hostnames = Hostnames.instance()
        hostnames.resolve(cluster, nodes)

        self.poutput(f"Cluster name : {cluster['ClusterName']}")
        self.poutput(f"Cluster Arn : {cluster['ClusterArn']}")
        self.poutput(f"Cluster status : {cluster['ClusterStatus']}")

        if "FailureMessage" in cluster and cluster["FailureMessage"]:
            self.poutput(f"Failure message : {cluster['FailureMessage']}")

        self.poutput("")

        max_hostname_len = 0
        for node in nodes:
            hostname = hostnames.get_hostname(node["InstanceId"])
            if hostname:
                max_hostname_len = max(max_hostname_len,len(hostname))

        format_string = "{:<%d} : {} : {:<%d} : {:<%d} : {} : {}" % (get_max_len(nodes,"InstanceGroupName"), max_hostname_len, get_max_len(nodes,("InstanceStatus","Status"))+1)

        for instance_group in cluster["InstanceGroups"]:
            for node in nodes:
                if node["InstanceGroupName"]==instance_group["InstanceGroupName"]:

                    instance_group_name = node["InstanceGroupName"]
                    node_id = node["InstanceId"]
                    hostname = hostnames.get_hostname(node_id)
                    if hostname is None:
                        hostname = ""
                    node_status = node["InstanceStatus"]["Status"]
                    ssm_target = f"sagemaker-cluster:{cluster_id}_{instance_group_name}-{node_id}"

                    if node_status in ["Pending"]:
                        node_status = "*" + node_status

                    self.poutput(format_string.format( instance_group_name, node_id, hostname, node_status, node["LaunchTime"].strftime("%Y/%m/%d %H:%M:%S"), ssm_target ))

                    if "Message" in node["InstanceStatus"] and node["InstanceStatus"]["Message"]:
                        message = node["InstanceStatus"]["Message"]
                        self.poutput("")
                        for line in message.splitlines():
                            self.poutput(line)
                        self.poutput("")
                        self.poutput("---")

    argparser.set_defaults(func=_do_describe)


    # ---

    argparser = subparsers1.add_parser("wait", help="Wait asynchronous cluster operations")
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", choices_provider=choices_cluster_names, nargs='?', default=None, help="Name of cluster. Wait instance level operations when specified.")

    def _do_wait(self, args):

        sagemaker_client = self.get_sagemaker_client()

        progress_dots = ProgressDots()

        if args.cluster_name is None:

            # Wait cluster creation/deletion
            while True:
                status_list = []
                clusters = list_clusters_all(sagemaker_client)
                for cluster in clusters:
                    if cluster["ClusterStatus"] not in ["InService","Failed"]:
                        status_list.append( cluster["ClusterName"] + ":" + cluster["ClusterStatus"] )

                progress_dots.tick(", ".join(status_list))

                if not status_list:
                    progress_dots.tick(None)
                    break

                time.sleep(5)

        else:

            # Wait instance creation/deletion
            while True:
                num_in_progress = 0
                status_list = []

                nodes = list_cluster_nodes_all( sagemaker_client, args.cluster_name )

                for node in nodes:

                    instance_group_name = node["InstanceGroupName"]
                    node_id = node["InstanceId"]
                    node_status = node["InstanceStatus"]["Status"]

                    if node_status not in ["Running","Failed"]:
                        status_list.append(f"{instance_group_name}:{node_id}:{node_status}")
                        num_in_progress += 1

                progress_dots.tick(", ".join(status_list))

                if num_in_progress==0:
                    progress_dots.tick(None)
                    break

                time.sleep(5)

    argparser.set_defaults(func=_do_wait)


    # ---

    argparser = subparsers1.add_parser("log", help="Print log from a cluster node")
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", choices_provider=choices_cluster_names, help="Name of cluster")
    argparser.add_argument("node_id", metavar="NODE_ID", action="store", choices_provider=choices_node_ids, help="Id of node")

    def _do_log(self, args):

        sagemaker_client = self.get_sagemaker_client()
        logs_client = self.get_logs_client()

        try:
            cluster = sagemaker_client.describe_cluster(
                ClusterName = args.cluster_name
            )
        except sagemaker_client.exceptions.ResourceNotFound:
            self.poutput(f"Cluster [{args.cluster_name}] not found.")
            return

        cluster_id = cluster["ClusterArn"].split("/")[-1]
        log_group = f"/aws/sagemaker/Clusters/{args.cluster_name}/{cluster_id}"

        try:
            streams = list_log_streams_all(logs_client, log_group)
        except logs_client.exceptions.ResourceNotFoundException:
            self.poutput(f"Log group [{log_group}] not found.")
            return

        # Convert hostname to node id
        if args.node_id.startswith("ip-"):
            nodes = list_cluster_nodes_all( sagemaker_client, args.cluster_name )
            hostnames = Hostnames.instance()
            hostnames.resolve(cluster, nodes)
            args.node_id = hostnames.get_node_id(args.node_id)

        found = False
        for stream in streams:
            if args.node_id=="*" or stream["logStreamName"].endswith(args.node_id):
                stream = stream["logStreamName"]
                
                header = f"--- {log_group} {stream} ---"
                self.poutput("-" * len(header))
                self.poutput(header)
                self.poutput("-" * len(header))
                logs.print_log(logs_client, log_group, stream)
                self.poutput(f"")

                found = True

        if not found:
            self.poutput(f"Log stream for [{args.node_id}] not found.")

    argparser.set_defaults(func=_do_log)


    # ---

    argparser = subparsers1.add_parser("ssm", help="Login to a cluster node with SSM")
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", choices_provider=choices_cluster_names, help="Name of cluster")
    argparser.add_argument("node_id", metavar="NODE_ID", action="store", choices_provider=choices_node_ids, help="Id of node")

    def _do_ssm(self, args):

        sagemaker_client = self.get_sagemaker_client()

        try:
            cluster = sagemaker_client.describe_cluster(
                ClusterName = args.cluster_name
            )
        except sagemaker_client.exceptions.ResourceNotFound:
            self.poutput(f"Cluster [{args.cluster_name}] not found.")
            return

        nodes = list_cluster_nodes_all( sagemaker_client, args.cluster_name )

        cluster_id = cluster["ClusterArn"].split("/")[-1]

        # Remove instance group name part
        if "/" in args.node_id:
            args.node_id = args.node_id.split("/")[-1]

        # Convert hostname to node id
        if args.node_id.startswith("ip-"):
            hostnames = Hostnames.instance()
            hostnames.resolve(cluster, nodes)
            args.node_id = hostnames.get_node_id(args.node_id)

        for node in nodes:
            instance_group_name = node["InstanceGroupName"]
            node_id = node["InstanceId"]
            if node_id==args.node_id:
                break
        else:
            self.poutput(f"Node ID [{args.node_id}] not found.")
            return

        ssm_target = f"sagemaker-cluster:{cluster_id}_{instance_group_name}-{node_id}"

        if 1:
            with self.sigint_protection:
                cmd = ["aws", "ssm", "start-session", "--target", ssm_target]
                subprocess.run(cmd)

        # use pexpect to automatically switch to ubuntu user
        elif 0:
            cmd = f"aws ssm start-session --target {ssm_target}"
            self.poutput(cmd)
            p = pexpect.spawn(cmd)
            p.expect("#")
            self.poutput(p.before.decode("utf-8") + p.after.decode("utf-8"), end="")

            def run_single_command(cmd):
                p.sendline(cmd)
                p.expect( ["#","$"] )
                self.poutput(p.before.decode("utf-8") + p.after.decode("utf-8"), end="")

            run_single_command(f"sudo su ubuntu")
            run_single_command(f"cd && bash")

            p.interact()

            p.terminate(force=True)

    argparser.set_defaults(func=_do_ssm)


    # ---

    argparser = subparsers1.add_parser("ssh", help="Set up SSH acccess to all cluster nodes")
    subparsers2 = argparser.add_subparsers(title="sub-commands")

    # ---

    argparser = subparsers2.add_parser('print-config', help='Print SSH config for cluster nodes')
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", choices_provider=choices_cluster_names, help="Name of cluster")

    def _do_ssh_print_config(self, args):

        sagemaker_client = self.get_sagemaker_client()

        try:
            cluster = sagemaker_client.describe_cluster(
                ClusterName = args.cluster_name
            )
        except sagemaker_client.exceptions.ResourceNotFound:
            self.poutput(f"Cluster [{args.cluster_name}] not found.")
            return
        
        nodes = list_cluster_nodes_all( sagemaker_client, args.cluster_name )

        cluster_id = cluster["ClusterArn"].split("/")[-1]

        if "AWS_PROFILE" in os.environ:
            profile = os.environ["AWS_PROFILE"]
        else:
            profile = "default"

        for instance_group in cluster["InstanceGroups"]:
            node_index = 0
            for node in nodes:
                if node["InstanceGroupName"]==instance_group["InstanceGroupName"]:

                    instance_group_name = node["InstanceGroupName"]
                    node_id = node["InstanceId"]

                    self.poutput("")                
                    self.poutput(
                        f"Host {args.cluster_name}-{instance_group_name}-{node_index}\n"
                        f"    HostName sagemaker-cluster:{cluster_id}_{instance_group_name}-{node_id}\n"
                        f"    User ubuntu\n"
                        f"    IdentityFile ~/keys/842413447717-ec2.pem\n"
                        f"    ProxyCommand aws --profile {profile} --region {get_region()} ssm start-session --target %h --document-name AWS-StartSSHSession --parameters portNumber=%p"
                    )

                    node_index += 1

        self.poutput("")

    argparser.set_defaults(func=_do_ssh_print_config)


    # ---

    argparser = subparsers2.add_parser('install-key', help='Install SSH public key to all cluster nodes')
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", choices_provider=choices_cluster_names, help="Name of cluster")
    argparser.add_argument("public_key_file", metavar="PUBLIC_KEY_FILE", action="store", completer=cmd2.Cmd.path_complete, help="SSH public key file")
    
    def _do_ssh_install_key(self, args):

        sagemaker_client = self.get_sagemaker_client()

        try:
            cluster = sagemaker_client.describe_cluster(
                ClusterName = args.cluster_name
            )
        except sagemaker_client.exceptions.ResourceNotFound:
            self.poutput(f"Cluster [{args.cluster_name}] not found.")
            return
        
        nodes = list_cluster_nodes_all( sagemaker_client, args.cluster_name )

        cluster_id = cluster["ClusterArn"].split("/")[-1]

        public_key_file = os.path.expanduser(args.public_key_file)

        with open(public_key_file) as fd:
            public_key = fd.read().strip()

        if len(public_key.splitlines()) > 1:
            self.poutput(f"Public key contains multiple lines unexpectedly.")
            return

        for node in nodes:
            instance_group_name = node["InstanceGroupName"]
            node_id = node["InstanceId"]
            ssm_target = f"sagemaker-cluster:{cluster_id}_{instance_group_name}-{node_id}"
            authorized_keys_path = os.path.join(self.hyperpod_config.home, self.hyperpod_config.username, ".ssh/authorized_keys")

            self.poutput(f"Installing ssh public key to {node_id} {authorized_keys_path}")

            p = pexpect.popen_spawn.PopenSpawn([*self.aws_config.awscli, "ssm", "start-session", "--target", ssm_target])
            p.expect("#")
            cmd = f"cat {authorized_keys_path}"
            p.sendline(cmd)
            p.expect("#")

            if public_key in p.before.decode("utf-8"):
                self.poutput("Already installed")
            else:
                cmd = f"echo {public_key} >> {authorized_keys_path}"
                p.sendline(cmd)
                p.expect("#")
                self.poutput("Done")

            p.kill(signal.SIGINT)

    argparser.set_defaults(func=_do_ssh_install_key)


    # ---

    argparser = subparsers1.add_parser("run", help="Run single line command in all nodes of specified instance group")
    argparser.add_argument("cluster_name", metavar="CLUSTER_NAME", action="store", choices_provider=choices_cluster_names, help="Name of cluster")
    argparser.add_argument("--instance-group-name", action="store", required=True, help="Instance group name")
    argparser.add_argument("--command", action="store", required=True, help="Single line of command to run")

    @cmd2.with_category(CATEGORY)
    @cmd2.with_argparser(argparser)
    def _do_run(self, args):

        sagemaker_client = self.get_sagemaker_client()

        try:
            cluster = sagemaker_client.describe_cluster(
                ClusterName = args.cluster_name
            )
        except sagemaker_client.exceptions.ResourceNotFound:
            self.poutput(f"Cluster [{args.cluster_name}] not found.")
            return
        
        nodes = list_cluster_nodes_all( sagemaker_client, args.cluster_name )

        cluster_id = cluster["ClusterArn"].split("/")[-1]

        for node in nodes:
            instance_group_name = node["InstanceGroupName"]

            if instance_group_name==args.instance_group_name:

                node_id = node["InstanceId"]
                ssm_target = f"sagemaker-cluster:{cluster_id}_{instance_group_name}-{node_id}"

                self.poutput(f"Running command in {node_id}")
                self.poutput("")

                p = pexpect.popen_spawn.PopenSpawn([*self.aws_config.awscli, "ssm", "start-session", "--target", ssm_target])
                p.expect("#")
                self.poutput(p.after.decode("utf-8"),end="")
                p.sendline(args.command)
                p.expect("#")
                self.poutput(p.before.decode("utf-8"),end="")
                p.kill(signal.SIGINT)

                self.poutput("-----")

    argparser.set_defaults(func=_do_run)

