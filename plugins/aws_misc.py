import os
import re
import time
import datetime
import tempfile
import gzip
import json
import shutil

import boto3


def get_boto3_client(service_name):

    region_name = None
    if "AWS_REGION" in os.environ:
        region_name = os.environ["AWS_REGION"]

    return boto3.client(service_name, region_name=region_name)


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


class LogsExporter:

    def __init__(self, logs_client, log_group, s3_path, start_datetime, end_datetime):
        self.logs_client = logs_client
        self.log_group = log_group
        self.s3_path = s3_path
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime

    def run(self):

        utcnow = datetime.datetime.utcnow()
        
        with tempfile.TemporaryDirectory() as export_dir:
            with tempfile.TemporaryDirectory() as plaintext_dir:
        
                # export logs
                self.exportSingleLogGroup( local_dirname=export_dir )
            
                # convert to plain text, sort, and normalize
                self.convertToPlainTextAndNormalize( export_dir, plaintext_dir )

                # create account info file
                self.createAccountInfoFile( plaintext_dir )
                
                # create a Zip file from plain text files
                self.createZipFile( plaintext_dir, "./exported_logs_%s" % utcnow.strftime("%Y%m%d_%H%M%S") )
                
    def splitS3Path( self, s3_path ):
        re_pattern_s3_path = "s3://([^/]+)/(.*)"
        re_result = re.match( re_pattern_s3_path, s3_path )
        bucket = re_result.group(1)
        key = re_result.group(2)
        key = key.rstrip("/")
        return bucket, key

    def exportSingleLogGroup( self, local_dirname ):

        # Export to S3

        s3_bucket, s3_prefix = self.splitS3Path(self.s3_path)
        
        start_datetime_utc = datetime.datetime.strptime( self.start_datetime, "%Y%m%d_%H%M%S" )
        end_datetime_utc = datetime.datetime.strptime( self.end_datetime, "%Y%m%d_%H%M%S" )

        response = self.logs_client.create_export_task(
            logGroupName = self.log_group,
            fromTime = int( start_datetime_utc.timestamp() * 1000 ),
            to = int( end_datetime_utc.timestamp() * 1000 ),
            destination = s3_bucket,
            destinationPrefix = s3_prefix,
        )
        
        export_task_id = response["taskId"]
        
        while True:
            
            completed = False
            response = self.logs_client.describe_export_tasks( taskId = export_task_id )
            
            for export_task in response["exportTasks"]:
                if export_task["taskId"] == export_task_id:
                    status_code = export_task["status"]["code"]
                    if "message" in export_task["status"]:
                        status_message = export_task["status"]["message"]
                    else:
                        status_message = ""
                    print( "Export task status :", status_code, status_message )
                    if status_code in ("COMPLETED", "CANCELLED", "FAILED"):
                        completed = True
            
            if completed: break
            
            time.sleep(10)
            
        # Download files to local
        
        s3 = get_boto3_client("s3")

        exported_s3_prefix = s3_prefix + "/" + export_task_id
        response = s3.list_objects_v2( Bucket = s3_bucket, Prefix=exported_s3_prefix )
        if "Contents" in response:
            for s3_object in response["Contents"]:
                
                exported_s3_key = s3_object["Key"]
                
                assert exported_s3_key.startswith( exported_s3_prefix )
                log_stream_name_and_filename = exported_s3_key[ len(exported_s3_prefix) : ].lstrip("/")
                
                downloaded_local_filepath = os.path.join( local_dirname, log_stream_name_and_filename )
                
                os.makedirs( os.path.split(downloaded_local_filepath)[0], exist_ok=True )
                
                print( "Downloading", exported_s3_key )
                
                s3.download_file(
                    Bucket = s3_bucket,
                    Key = exported_s3_key,
                    Filename = downloaded_local_filepath,
                )

    def convertToPlainTextAndNormalize( self, src_dirname, dst_dirname ):

        for place, dirs, files in os.walk( src_dirname ):

            line_group_list = []

            # read all .gz files under a single log stream
            for filename in files:
                if filename.endswith(".gz"):

                    src_filepath = os.path.join( place, filename )

                    assert src_filepath.startswith( src_dirname )
                    
                    print( "Reading :", src_filepath )
                    
                    with gzip.open( src_filepath ) as fd_gz:
                        d = fd_gz.read()
                    
                    lines = d.splitlines()
                    for line in lines:
                        # format: 2022-06-24T16:50:57.033Z
                        re_result = re.match( rb"[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-9]{2}\:[0-9]{2}\:[0-9]{2}\.[0-9]{3}Z .*", line )
                        if re_result is not None:
                            line_group_list.append( [ line ] )
                        else:
                            #assert len(line)==0 or line.startswith(b"\t") or line.startswith(b" "), str([ line ])
                            line_group_list[-1].append(line)

            # sort lines and write a log file at log stream level
            if line_group_list:
                
                dst_filepath = os.path.join( dst_dirname, place[len(src_dirname):].lstrip("/\\") + ".log" )

                print( "Writing", dst_filepath )

                line_group_list.sort()
                lines = []
                for line_group in line_group_list:
                    lines += line_group
                d = b"\n".join(lines)               
                
                # Normalize                
                d = d.replace( b"\0", b"\\0" )
                
                os.makedirs( os.path.split(dst_filepath)[0], exist_ok=True )
                with open( dst_filepath, "wb" ) as fd_log:
                    fd_log.write(d)

    def createAccountInfoFile( self, dirname ):

        sts = get_boto3_client("sts")

        account_id = sts.get_caller_identity()["Account"]
        region_name = sts.meta.region_name

        filename = os.path.join( dirname, "info.json" )
        with open( filename, "w" ) as fd:
            d = {
                "account_id" : account_id,
                "region_name" : region_name,
            }

            fd.write( json.dumps(d) )

    def createZipFile( self, dirname_to_zip, zip_filename_wo_ext ):

        print( "Creating a Zip file", zip_filename_wo_ext + ".zip" )
        shutil.make_archive( zip_filename_wo_ext, 'zip', dirname_to_zip )

