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

#!/usr/bin/env python3

import aws_cdk as cdk

from constants import PRIMARY_REGION, SECONDARY_REGION, ACCOUNT_ID
from sagemaker_domain_dr.sagemaker_domain_dr_stack import SagemakerDomainDrStack
from ecs_dr_recovery.ecs_dr_recovery_stack import ECSTaskStack


DISASTER_RECOVERY = True

app = cdk.App()

env_primary_region = cdk.Environment(account=ACCOUNT_ID, region=PRIMARY_REGION)
SagemakerDomainDrStack(app, "SagemakerDomainPrimaryStack", env=env_primary_region)

if DISASTER_RECOVERY:
    env_secondary_region = cdk.Environment(account=ACCOUNT_ID, region=SECONDARY_REGION)
    SagemakerDomainDrStack(app, "SagemakerDomainSecondaryStack", env=env_secondary_region)
    ECSTaskStack(app, "ECSTaskStack", env=env_secondary_region)

app.synth()
