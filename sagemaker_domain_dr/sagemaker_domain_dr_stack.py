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

from constructs import Construct
from aws_cdk import (
    aws_lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_dynamodb as dynamodb,
    aws_sagemaker as sagemaker,
    aws_ssm as ssm,
    Stack,
    Duration,
    RemovalPolicy,
)
from constants import PRIMARY_REGION, SECONDARY_REGION, NUMBER_USERS


TABLE_PRIMARY_KEY = "UserProfileName"


class SagemakerDomainDrStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        flag = "Primary" if self.region == PRIMARY_REGION else "Secondary"
        # Default VPC
        default_vpc = ec2.Vpc.from_lookup(self, id="DefaultVPC", is_default=True)
        # Sagemaker Domain
        role_sagemaker_studio_domain = iam.Role(
            self,
            f"RoleFor{flag}SagemakerStudioUsers",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            role_name=f"Role{flag}SagemakerStudioUsers",
            managed_policies=[
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    id="SagemakerFullAccess",
                    managed_policy_arn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
                ),
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    id="S3FullAccess",
                    managed_policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
                )
            ],
        )
        domain = sagemaker.CfnDomain(
            self,
            f"{flag}SagemakerDomain",
            auth_mode="IAM",
            default_user_settings=sagemaker.CfnDomain.UserSettingsProperty(
                execution_role=role_sagemaker_studio_domain.role_arn
            ),
            domain_name=f"sagemaker-domain-{flag}",
            vpc_id=default_vpc.vpc_id,
            subnet_ids=default_vpc.select_subnets().subnet_ids,
        )
        ssm.StringParameter(
            self,
            f"{flag}SagemakerDomainId",
            parameter_name=f"/SagemakerDomain/{flag}/DomainId",
            string_value=domain.attr_domain_id
        )
        ssm.StringParameter(
            self,
            f"{flag}OriginalEFSId",
            parameter_name=f"/SagemakerDomain/{flag}/Original/EfsId",
            string_value=domain.attr_home_efs_file_system_id
        )

        # DynamoDB Table
        uid_tracker_table = dynamodb.Table(
            self,
            f"UIDTrackerTable{flag}",
            table_name=f"{domain.domain_name}-UID-tracker",
            partition_key=dynamodb.Attribute(
               name=TABLE_PRIMARY_KEY,
               type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            replication_regions=[SECONDARY_REGION] if self.region == PRIMARY_REGION else None
        )
        ssm.StringParameter(
            self,
            f"{flag}DynamoDBTableNameParameter",
            parameter_name=f"/DynamoDB/UIDTracker/{flag}",
            string_value=uid_tracker_table.table_name
        )

        # Lambda Function
        user_profile_persistence_lambda = aws_lambda.Function(
            self,
            f"{flag}UserProfilePersistenceLambda",
            code=aws_lambda.Code.from_asset("sagemaker_domain_dr/user_profile_persist_lambda"),
            handler="user_profile_persistence.lambda_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_10,
            description=f"Lambda function to track {flag} sagemaker domain "
                        f"UserProfileName to UID mapping",
            function_name=f"{flag}-sagemaker-domain-UID-tracker-lambda-function",
            environment={
                "PRIMARY_REGION": PRIMARY_REGION,
                "SECONDARY_REGION": SECONDARY_REGION,
                "TABLE_NAME": uid_tracker_table.table_name,
                "TABLE_PRIMARY_KEY": TABLE_PRIMARY_KEY,
            },
            timeout=Duration.seconds(900),
        )

        describe_domain_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=[f"arn:aws:sagemaker:{self.region}:{self.account}:domain/{domain.attr_domain_id}"],
            actions=["sagemaker:DescribeDomain"]
        )
        user_profile_persistence_lambda.add_to_role_policy(describe_domain_policy)
        describe_user_profile_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=[f"arn:aws:sagemaker:{self.region}:{self.account}:user-profile/{domain.attr_domain_id}/*"],
            actions=["sagemaker:DescribeUserProfile"]
        )
        user_profile_persistence_lambda.add_to_role_policy(describe_user_profile_policy)
        dynamodb_write_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=[f"arn:aws:dynamodb:{self.region}:{self.account}:table/{uid_tracker_table.table_name}"],
            actions=["dynamodb:PutItem", "dynamodb:DeleteItem"]
        )
        user_profile_persistence_lambda.add_to_role_policy(dynamodb_write_policy)
        efs_replica_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=[
                f"arn:aws:elasticfilesystem:{self.region}:{self.account}:file-system/"
                f"{domain.attr_home_efs_file_system_id}"
            ],
            actions=[
                "elasticfilesystem:DescribeReplicationConfigurations",
                "elasticfilesystem:CreateReplicationConfiguration"
            ]
        )
        user_profile_persistence_lambda.add_to_role_policy(efs_replica_policy)
        efs_create_fs_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=["*"],
            actions=["elasticfilesystem:CreateFileSystem"]
        )
        user_profile_persistence_lambda.add_to_role_policy(efs_create_fs_policy)
        ssm_put_param_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=[
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/"
                f"SagemakerDomain/{flag}/Replica/EfsId"
            ],
            actions=["ssm:PutParameter"]
        )
        user_profile_persistence_lambda.add_to_role_policy(ssm_put_param_policy)

        create_service_linked_role_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=["*"],
            actions=[
                "iam:CreateServiceLinkedRole",
            ]
        )
        user_profile_persistence_lambda.add_to_role_policy(create_service_linked_role_policy)

        # Event Trigger
        user_profile_creation_rule = events.Rule(
            self,
            f"{flag}UserProfileEventRule",
            description="UserProfileEventRule",
            event_pattern=events.EventPattern(
                source=["aws.sagemaker"],
                detail_type=["AWS API Call via CloudTrail"],
                detail={
                    "eventSource": ["sagemaker.amazonaws.com"],
                    "eventName": ["CreateUserProfile", "DeleteUserProfile"]
                }
            ),
            rule_name=f"{flag}UserProfileEventRule"
        )
        user_profile_creation_rule.add_target(
            targets.LambdaFunction(user_profile_persistence_lambda)
        )

        # Sagemaker User Profiles - here can i chagne how many users are created? 
        if self.region == PRIMARY_REGION:
            user_profile_name_list = [f"sagemaker-user-{i}" for i in range(NUMBER_USERS)]
        elif self.region == SECONDARY_REGION:
            user_profile_name_list = [f"sagemaker-user-{i}" for i in range(NUMBER_USERS)][::-1]
        for name in user_profile_name_list:
            cfn_temp_user_profile = sagemaker.CfnUserProfile(
                self,
                f"{name}-UserProfile",
                domain_id=domain.attr_domain_id,
                user_profile_name=name
            )
            cfn_temp_user_profile.add_dependency(uid_tracker_table.node.default_child)
            cfn_temp_user_profile.add_dependency(user_profile_persistence_lambda.node.default_child)
            cfn_temp_user_profile.add_dependency(user_profile_creation_rule.node.default_child)



