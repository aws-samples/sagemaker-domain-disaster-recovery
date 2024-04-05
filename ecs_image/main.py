"""
 Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 SPDX-License-Identifier: MIT-0

 Permission is hereby granted, free of charge, to any person obtaining a copy of this
 software and associated documentation files (the "Software"), to deal in the Software
 without restriction, including without limitation the rights to use, copy, modify,
 merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 permit persons to whom the Software is furnished to do so.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import os
import subprocess
import boto3

TABLE_PRIMARY_KEY = "UserProfileName"
PRIMARY_UID_TRACKER_TABLE_NAME = os.environ["PRIMARY_UID_TRACKER_TABLE_NAME"]
SECONDARY_UID_TRACKER_TABLE_NAME = os.environ["SECONDARY_UID_TRACKER_TABLE_NAME"]
SECONDARY_SAGEMAKER_DOMAIN_ID = os.environ["SECONDARY_SAGEMAKER_DOMAIN_ID"]

dynamodb_client = boto3.client("dynamodb")
sagemaker_client = boto3.client("sagemaker")


def get_user_profile_uid(user_profile_name: str):
    source_item_response = dynamodb_client.get_item(
        TableName=PRIMARY_UID_TRACKER_TABLE_NAME,
        Key={TABLE_PRIMARY_KEY: {"S": user_profile_name}}
    )
    if "Item" in source_item_response:
        source_uid = source_item_response["Item"]["UID"]["S"]
        print(f"UserProfile {user_profile_name} source UID: {source_uid}")
    else:
        source_uid = ""
        print(f"UserProfile {user_profile_name} source UID not found in {PRIMARY_UID_TRACKER_TABLE_NAME}.")
    target_item_response = dynamodb_client.get_item(
        TableName=SECONDARY_UID_TRACKER_TABLE_NAME,
        Key={TABLE_PRIMARY_KEY: {"S": user_profile_name}}
    )
    if "Item" in target_item_response:
        target_uid = target_item_response["Item"]["UID"]["S"]
        print(f"UserProfile {user_profile_name} target UID: {target_uid}")
    else:
        target_uid = ""
        print(f"UserProfile {user_profile_name} target UID not found in {SECONDARY_UID_TRACKER_TABLE_NAME}.")
    return source_uid, target_uid


def sync_dir(source_uid: str, target_uid: str):
    source_dir = f"/source_efs/{source_uid}/"
    print(f"source_dir_list: {os.listdir(source_dir)}")
    target_dir = f"/target_efs/{target_uid}"
    if not os.path.exists(target_dir):
        print(f"Create Dir {target_dir}")
        os.mkdir(target_dir)
    print(f"target_dir_list: {os.listdir(target_dir)}")
    subprocess.run(
        ["rsync", "-a", "--ignore-existing", "--exclude", ".*", source_dir, target_dir],
        stdout=subprocess.PIPE
    )
    print(f"target_dir_list_after_sync: {os.listdir(target_dir)}")
    print("Owner before change")
    stat_info = os.stat(source_dir)
    uid = stat_info.st_uid
    gid = stat_info.st_gid
    print(uid, gid)
    subprocess.call(["chown", "-R", target_uid, target_dir])
    print("Owner after change")
    stat_info = os.stat(target_dir)
    uid = stat_info.st_uid
    gid = stat_info.st_gid
    print(uid, gid)


def workspace_recovery():
    response = sagemaker_client.list_user_profiles(
        DomainIdEquals=SECONDARY_SAGEMAKER_DOMAIN_ID
    )
    user_profile_name_list = [
        item["UserProfileName"] for item in response["UserProfiles"] if item["Status"] == "InService"
    ]
    print(f"UserProfileName List: {user_profile_name_list}")
    print(f"Source UID List: {os.listdir('/source_efs')}")
    print(f"Target UID List: {os.listdir('/target_efs')}")
    for user_profile_name in user_profile_name_list:
        temp_source_uid, temp_target_uid = get_user_profile_uid(user_profile_name)
        if temp_source_uid and temp_target_uid and os.path.exists(f"/source_efs/{temp_source_uid}/"):
            sync_dir(source_uid=temp_source_uid, target_uid=temp_target_uid)
        else:
            print(
                f"{user_profile_name} doesn't have a directory in EFS. "
                f"Studio may not launched yet for this user."
            )
    print("Workspace recovered.")


if __name__ == "__main__":
    workspace_recovery()
