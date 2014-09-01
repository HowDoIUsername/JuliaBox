import os, sys, time, errno
import boto.dynamodb, boto.utils, boto.ec2.cloudwatch
from boto.s3.key import Key


def log_info(s):
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    print (ts + "  " + s)
    sys.stdout.flush()

def esc_sessname(s):
    return s.replace("@", "_at_").replace(".", "_")

def read_config():
    with open("conf/tornado.conf") as f:
        cfg = eval(f.read())

    if os.path.isfile("conf/jbox.user"):
        with open("conf/jbox.user") as f:
            ucfg = eval(f.read())
        cfg.update(ucfg)

    cfg["admin_sessnames"]=[]
    for ad in cfg["admin_users"]:
        cfg["admin_sessnames"].append(esc_sessname(ad))

    cfg["protected_docknames"]=[]
    for ps in cfg["protected_sessions"]:
        cfg["protected_docknames"].append("/" + esc_sessname(ps))

    return cfg

def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def unquote(s):
    s = s.strip()
    if s[0] == '"':
        return s[1:-1]
    else:
        return s

class CloudHelper:
    REGION = 'us-east-1'
    INSTALL_ID = 'JuliaBox'
    DYNAMODB_CONN = None
    S3_CONN = None
    S3_BUCKETS = {}
    CLOUDWATCH_CONN = None
    ENABLED = {}
    
    @staticmethod
    def configure(has_s3=True, has_dynamodb=True, has_cloudwatch=True, region='us-east-1', install_id='JuliaBox'):
        CloudHelper.ENABLED['s3'] = has_s3
        CloudHelper.ENABLED['dynamodb'] = has_dynamodb
        CloudHelper.ENABLED['cloudwatch'] = has_cloudwatch
        CloudHelper.INSTALL_ID = install_id
        CloudHelper.REGION = region
    
    @staticmethod
    def connect_dynamodb():
        """ Return a connection to AWS DynamoDB at the configured region """
        if (None == CloudHelper.DYNAMODB_CONN) and CloudHelper.ENABLED['dynamodb']:
            CloudHelper.DYNAMODB_CONN = boto.dynamodb.connect_to_region(CloudHelper.REGION)
        return CloudHelper.DYNAMODB_CONN
    
    @staticmethod
    def connect_s3():
        if (None == CloudHelper.S3_CONN) and CloudHelper.ENABLED['s3']:
            CloudHelper.S3_CONN = boto.connect_s3()    
        return CloudHelper.S3_CONN
    
    @staticmethod
    def connect_s3_bucket(bucket):
        if not CloudHelper.ENABLED['s3']:
            return None

        if bucket not in CloudHelper.S3_BUCKETS:
            CloudHelper.S3_BUCKETS[bucket] = CloudHelper.connect_s3().get_bucket(bucket)
        return CloudHelper.S3_BUCKETS[bucket]
    
    @staticmethod
    def connect_cloudwatch():
        if (None == CloudHelper.CLOUDWATCH_CONN) and CloudHelper.ENABLED['cloudwatch']:
            CloudHelper.CLOUDWATCH_CONN = boto.ec2.cloudwatch.connect_to_region(CloudHelper.REGION)
        return CloudHelper.CLOUDWATCH_CONN
    
    @staticmethod
    def publish_stats(stat_name, stat_unit, stat_value):
        """ Publish custom cloudwatch statistics. Used for status monitoring and auto scaling. """
        if not CloudHelper.ENABLED['cloudwatch']:
            return
        
        instance_id = boto.utils.get_instance_metadata()['instance-id']
        dims = {'InstanceID': instance_id}
        log_info("CloudWatch " + CloudHelper.INSTALL_ID + ": " + stat_name + " = " + str(stat_value) + " " + stat_unit)
        CloudHelper.connect_cloudwatch().put_metric_data(namespace=CloudHelper.INSTALL_ID, name=stat_name, unit=stat_unit, value=stat_value, dimensions=dims)
    
    @staticmethod
    def push_file_to_s3(bucket, local_file, metadata={}, encrypt=False):
        if not CloudHelper.ENABLED['s3']:
            return None
        
        key_name = os.path.basename(local_file)
        k = Key(CloudHelper.connect_s3_bucket(bucket))
        k.key = key_name
        for meta_name,meta_value in metadata.iteritems():
            k.set_metadata(meta_name, meta_value)
        k.set_contents_from_filename(local_file)
        return k

    @staticmethod    
    def pull_file_from_s3(bucket, local_file, metadata_only=False):
        if not CloudHelper.ENABLED['s3']:
            return None
        
        key_name = os.path.basename(local_file)
        k = CloudHelper.connect_s3_bucket(bucket).get_key(key_name)
        if (k != None) and (not metadata_only):
            k.get_contents_to_filename(local_file)
        return k