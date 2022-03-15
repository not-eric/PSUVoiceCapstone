import logging
import os
import boto3
import json
from botocore.exceptions import ClientError

def create_presigned_url(object_name):
    """Generate a presigned URL to share an S3 object with a capped expiration of 60 seconds

    :param object_name: string
    :return: Presigned URL as string. If error, returns None.
    """
    s3_client = boto3.client('s3',
                             region_name=os.environ.get('S3_PERSISTENCE_REGION'),
                             config=boto3.session.Config(signature_version='s3v4',s3={'addressing_style': 'path'}))
    try:
        bucket_name = os.environ.get('S3_PERSISTENCE_BUCKET')
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=60*1)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response


def read_file(file_name):
    """ Read the contents of a file stored in s3 
    
    :param file_name: string
    :return: Contents of the file as a string
    """
    try:
        client = boto3.client('s3')
        bucket_name = os.environ.get("S3_PERSISTENCE_BUCKET")
        file = client.get_object(Bucket=bucket_name, Key=file_name)
        return file["Body"].read().decode("utf-8")
        
    except ClientError as e:
        logging.error(e)
        return None
    
def write_file(file_name, content):
    try:
        client = boto3.client('s3')
        bucket_name = os.environ.get("S3_PERSISTENCE_BUCKET")
        return client.put_object(Bucket=bucket_name, Key=file_name, Body=content)
        
    except ClientError as e:
        logging.error(e)
        return None

def get_keys_from_objects(response_contents):
    """ Convert a list of s3 objects into a list of file names
    
    :param response_contents: list of s3 object metadata
    :return: File names as a list of strings
    """
    for i in response_contents:
        yield i['Key']

def list_folder_contents(path):
    try:
        client = boto3.client('s3')
        bucket_name = os.environ.get("S3_PERSISTENCE_BUCKET")
        response = client.list_objects_v2(Bucket=bucket_name, Prefix=path)
        return list(get_keys_from_objects(response['Contents']))
    
    except ClientError as e:
        logging.error(e)
        return None

def list_file_names(path):
    file_list = []
    recordings = list_folder_contents(path)[1:]
    if len(recordings) > 0:
        for file in recordings:
            file_name = file.split('/')[-1]
            file_name = file_name[:file_name.index('.')]
            file_list.append(file_name)
        return file_list
    
    return False

def does_file_exists(file_name, path):
    folder_contents = list_folder_contents(path)
    for i in folder_contents:
        if file_name in i:
            return True
    
    return False

def does_user_exist(user_name):
    """ Determine if a given username already exists in the user directory in S3
    
    :param user_name: string
    :return: If the user was found as a boolean
    """
    if user_name:
        user_list = list_folder_contents("Media/users/")
        for i in user_list:
            if user_name in i:
                return True
    
    return False

def create_new_user(user_name):
    """ Generate a new user in the S3 bucket
    
    :param user_name: string
    :return: Successful creation as a boolean
    """
    
    file_body = '''
    {
        "pending_requests": [],
        "denied_requests": [],
        "preferences": {}
    }
    '''
    privacy_preferences_key = "Media/users/" + user_name + "/privacy_preferences.json"
    recordings_key = "Media/users/" + user_name + "/recordings/"
    write_file(privacy_preferences_key, file_body)
    return write_file(recordings_key, "")

def sign_in(handler_input, user_name):
    handler_input.attributes_manager.persistent_attributes['current_user'] = user_name
    handler_input.attributes_manager.save_persistent_attributes()

def sign_out(handler_input):
    handler_input.attributes_manager.delete_persistent_attributes()

def is_logged_in(handler_input):
    return ('current_user' in handler_input.attributes_manager.persistent_attributes)

def get_current_user(handler_input):
    return handler_input.attributes_manager.persistent_attributes['current_user']

def make_request(requester, requestee, request_type, reason):
    
    privacy_key = "Media/users/" + requestee + "/privacy_preferences.json"
    privacy_object = json.loads(read_file(privacy_key))
    request_object = next(filter(lambda request: request["requester"] == requester, privacy_object["pending_requests"]), None)
    if request_object is None:
        request_object = {
            "requester": requester,
            "request_type": request_type,
            "reason": reason
        }
        privacy_object['pending_requests'].append(request_object)
        return write_file(privacy_key, json.dumps(privacy_object))
    else:
        return False

def deny_request(requestee, requester):
    privacy_key = "Media/users/" + requestee + "/privacy_preferences.json"
    privacy_object = json.loads(read_file(privacy_key))
    request_object = next(filter(lambda request: request["requester"] == requester, privacy_object["pending_requests"]), None)
    if request_object is not None:
        privacy_object["denied_requests"].append(request_object)
        privacy_object["pending_requests"].remove(request_object)
        return write_file(privacy_key, json.dumps(privacy_object))
    else:
        return False

def accept_request(requestee, requester, file_name=None):
    
    privacy_key = "Media/users/" + requestee + "/privacy_preferences.json"
    privacy_object = json.loads(read_file(privacy_key))
    request_object = next(filter(lambda request: request["requester"] == requester, privacy_object["pending_requests"]), None)
    if request_object is not None:
        privacy_object["pending_requests"].remove(request_object)
        if file_name is None:
            # check if user has already accepted a request for all files before
            if not hasattr(privacy_object["preferences"], "all_files"):
                privacy_object["preferences"]["all_files"] = []
            
            privacy_object["preferences"]["all_files"].append(request_object)
        else:
            if not hasattr(privacy_object["preferences"], file_name):
                privacy_object["preferences"][file_name] = []
            
            privacy_object["preferences"][file_name].append(request_object)
        
        write_file(privacy_key, json.dumps(privacy_object))
        return request_object
    else:
        return False

def revoke_access(requestee, requester, request_type=None, reason=None):
    privacy_key = "Media/users/" + requestee + "/privacy_preferences.json"
    privacy_object = json.loads(read_file(privacy_key))
    accesses_revoked = []
    for file in privacy_object["preferences"].keys():
        for access_object in privacy_object["preferences"][file]:
            validator = True
            if access_object["requester"] == requester:
                if request_type != None and access_object["request_type"] != request_type:
                    validator = False
                if reason != None and access_object["reason"] != reason:
                    validator = False
            else:
                validator = False
            
            if validator == True:
                privacy_object["preferences"][file].remove(access_object)
                privacy_object["denied_requests"].append(access_object)
                accesses_revoked.append(access_object)
    
    write_file(privacy_key, json.dumps(privacy_object))
    return accesses_revoked

def list_access_from(requester, requestee):
    privacy_key = "Media/users/" + requestee + "/privacy_preferences.json"
    privacy_preferences = json.loads(read_file(privacy_key))["preferences"]
    access_objects = [] # list of tuples like: (file_name, access_objects)
    for f in privacy_preferences.keys():
        access_objects.append(( f, list(filter(lambda ao: ao["requester"] == requester, privacy_preferences[f])) ))
    
    return access_objects

def list_all_access(requester):
    access_dictionary = {}
    paths_to_check = list(filter(lambda path: requester not in path and "privacy_preferences.json" in path, list_folder_contents("Media/users/")))
    users_to_check = [privacy_key.replace("Media/users/", "").replace("/privacy_preferences.json", "") for privacy_key in paths_to_check]
    for user in users_to_check:
        access_dictionary[user] = list_access_from(requester, user)
    
    return access_dictionary

def list_requests(user_name):
    requests_key = "Media/users/" + user_name + "/privacy_preferences.json"
    requests = json.loads(read_file(requests_key))['pending_requests']

    return [ f"{x['requester']} has a {x['reason']} project and has asked for \
                permission to {x['request_type']} using your recordings. " for x in requests]

def list_preferences(user):
    privacy_key = "Media/users/" + user + "/privacy_preferences.json"
    preferences = json.loads(read_file(privacy_key))["preferences"]
    permissions_list = []
    for f in preferences.keys():
        for access in preferences[f]:
            if f == "all_files":
                file = "all files"
            else:
                file = f
            
            permissions_list.append(f"{access['requester']} has access to {access['request_type']} using {file} for {access['reason']} purposes.")
    
    return permissions_list

def add_recording(user_name, file_name):
    """ Adds a new audio recording to the users recordings directory. If the
        file already exists, it will rename the file to {file_name}_1

    """
    file_key = "Media/sample_recordings/" + file_name
    recordings_key = "Media/users/" + user_name + "/recordings/"
    try: 
        if does_file_exists(file_name, recordings_key):
            # File w/ same name already exists, so change the name
            idx = file_name.index('.')
            file_name = file_name[:idx] + "_1" + file_name[idx:]
            
        client = boto3.client('s3')
        bucket_name = os.environ.get("S3_PERSISTENCE_BUCKET")
        recording = client.get_object(Bucket=bucket_name, Key=file_key)
        
        return write_file(recordings_key + file_name, recording['Body'].read())

    except ClientError as e:
        logging.error(e)
        return False

