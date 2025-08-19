import os

import concurrent.futures
import boto3

import misc


def get_region():

    if "AWS_REGION" in os.environ:
        return os.environ["AWS_REGION"]
    
    boto3_session = boto3.session.Session()
    region = boto3_session.region_name
    return region


def list_clusters_all(sagemaker_client):

    clusters = []    
    next_token = None

    while True:
        
        params = {}
        if next_token:
            params["NextToken"] = next_token

        response = sagemaker_client.list_clusters(**params)

        clusters += response["ClusterSummaries"]

        if "NextToken" in response and response["NextToken"]:
            next_token = response["NextToken"]
            continue

        break

    return clusters


def list_cluster_nodes_all(sagemaker_client, cluster_name):

    nodes = []
    next_token = None

    while True:
        
        params = {
            "ClusterName" : cluster_name
        }
        if next_token:
            params["NextToken"] = next_token

        response = sagemaker_client.list_cluster_nodes(**params)

        nodes += response["ClusterNodeSummaries"]

        if "NextToken" in response and response["NextToken"]:
            next_token = response["NextToken"]
            continue

        break

    return nodes


def list_cluster_events_all(sagemaker_client, cluster_name):

    events = []
    next_token = None

    while True:
        
        params = {
            "ClusterName" : cluster_name
        }
        if next_token:
            params["NextToken"] = next_token

        response = sagemaker_client.list_cluster_events(**params)

        events += response["Events"]

        if "NextToken" in response and response["NextToken"]:
            next_token = response["NextToken"]
            continue

        break

    return events


def list_log_streams_all(logs_client, log_group):

    streams = []
    next_token = None

    while True:
        
        params = {
            "logGroupName" : log_group,
            "limit" : 50,
        }
        if next_token:
            params["nextToken"] = next_token

        response = logs_client.describe_log_streams(**params)

        streams += response["logStreams"]

        if "nextToken" in response and response["nextToken"]:
            next_token = response["nextToken"]
            continue

        break

    return streams


class Hostnames:

    _instance = None

    @staticmethod
    def instance():
        if Hostnames._instance is None:
            Hostnames._instance = Hostnames()
        return Hostnames._instance

    def __init__(self):

        user_config = misc.UserConfig.instance()
        self.aws_config = user_config.get("AwsConfig")

        self.node_id_to_hostname = {}
        self.hostname_to_node_id = {}

    def resolve(self, sagemaker_client, cluster, nodes):

        cluster_name = cluster["ClusterName"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as thread_pool:
            
            def resolve_hostname(node):

                node_id = node["InstanceId"]

                if node_id in self.node_id_to_hostname and self.node_id_to_hostname[node_id]:
                    return self.node_id_to_hostname[node_id]
                
                response = sagemaker_client.describe_cluster_node(ClusterName=cluster_name, NodeId=node_id)
                hostname = response["NodeDetails"]["PrivateDnsHostname"].split(".")[0]

                return hostname

            for node, hostname in zip( nodes, thread_pool.map(resolve_hostname, nodes) ):
                node_id = node["InstanceId"]
                self.node_id_to_hostname[node_id] = hostname
                self.hostname_to_node_id[hostname] = node_id

    def get_hostname(self, node_id):
        return self.node_id_to_hostname[node_id]

    def get_node_id(self, hostname):
        return self.hostname_to_node_id[hostname]


def get_max_len( d, keys ):

    if not isinstance( keys, (list,tuple) ):
        keys = [keys]

    max_len = 0
    for item in d:
        for k in keys:
            item = item[k]
        max_len = max(len(item),max_len)
    return max_len


class ProgressDots:

    def __init__(self):
        self.status = None

    def tick(self,status):

        if self.status != status:

            # first line doesn't require line break
            if self.status is not None:
                print()

            self.status = status

            # print new status if not ending
            if self.status is not None:
                print(self.status, end=" ", flush=True)

            return

        # print dots if status didn't change
        if self.status is not None:
            print(".", end="", flush=True)
