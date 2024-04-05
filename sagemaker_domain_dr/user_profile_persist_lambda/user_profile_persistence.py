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

import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["TABLE_NAME"]
TABLE_PRIMARY_KEY = os.environ["TABLE_PRIMARY_KEY"]
PRIMARY_REGION = os.environ["PRIMARY_REGION"]
SECONDARY_REGION = os.environ["SECONDARY_REGION"]

sagemaker_client = boto3.client("sagemaker")
dynamodb_client = boto3.client("dynamodb")
efs_client = boto3.client("efs")
ssm_client = boto3.client("ssm")


def create_cross_region_replica_if_not_exist(domain_id):
    efs_id = sagemaker_client.describe_domain(
        DomainId=domain_id
    )["HomeEfsFileSystemId"]
    logger.info(f"EFS_ID: {efs_id}")
    try:
        replica_description = efs_client.describe_replication_configurations(
            FileSystemId=efs_id,
        )
        logger.info(f"Found EFS replication {replica_description}")
    except efs_client.exceptions.ReplicationNotFound:
        logger.info(f"No EFS replication found for {efs_id}.")
        response = efs_client.create_replication_configuration(
            SourceFileSystemId=efs_id,
            Destinations=[{"Region": SECONDARY_REGION}]
        )
        replica_efs_id = response["Destinations"][0]["FileSystemId"]
        logger.info(f"EFS replication {replica_efs_id} created for source {efs_id}.")
        ssm_client.put_parameter(
            Name="/SagemakerDomain/Primary/Replica/EfsId",
            Description=f"Sagemaker Domain Replicated EFS ID in {SECONDARY_REGION}",
            Value=replica_efs_id,
            Type="String",
            Overwrite=True,
        )


def lambda_handler(event, context):
    event_time = event["time"]
    current_region = event["region"]
    event_detail = event["detail"]
    create_time = event_detail["eventTime"]
    event_name = event_detail["eventName"]
    domain_id = event_detail["requestParameters"]["domainId"]
    user_profile_name = event_detail["requestParameters"]["userProfileName"]

    if current_region == PRIMARY_REGION:
        create_cross_region_replica_if_not_exist(domain_id)

    if event_name == "DeleteUserProfile":
        dynamodb_client.delete_item(
            TableName=TABLE_NAME,
            Key={TABLE_PRIMARY_KEY: {"S": user_profile_name}}
        )
        logger.info(f"{user_profile_name} deleted.")
    elif event_name == "CreateUserProfile":
        response = sagemaker_client.describe_user_profile(
            DomainId=domain_id,
            UserProfileName=user_profile_name
        )
        user_profile_uid = response["HomeEfsFileSystemUid"]
        logger.info(f"New sagemaker profile {user_profile_name}: {user_profile_uid} found.")
        dynamodb_client.put_item(
            TableName=TABLE_NAME,
            Item={
                TABLE_PRIMARY_KEY: {"S": user_profile_name},
                "UID": {"S": user_profile_uid},
                "CreationTime": {"S": create_time},
                "LastUpdateTime": {"S": event_time}
            }
        )
        logger.info(f"Item {user_profile_name}: {user_profile_uid} created.")
