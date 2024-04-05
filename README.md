# SageMaker Studio Domain DR Module

---

## Contents

* [Disaster Recovery Modes](#sagemaker-domain-dr-mode)
* [Deployment](#deployment)
* [Authors and Reviewers](#authors-and-reviewers)
* [License Summary](#license-summary)

---

## Sagemaker Domain DR Mode
### Active-Passive Mode
In this scenario, SageMaker Studio Domain is not setup in DR Region but cross region replication is enabled 
on the attached EFS. 
<br />
<br />
![Active-Passive-1](./assets/SagemakerDomainDrActivePassive-1.png "Hello")
<br />
<br />
When needed Studio Domain is spun up in DR Region and a step function is used to sync data 
from primary region's EFS Replica to DR region's Studio Domain EFS.
<br />
<br />
![Active-Passive-2](./assets/SagemakerDomainDrActivePassive-2.png)
### Active-Active Mode
In this scenario, SageMaker Studio Domain is set up in both Primary Region and DR Region, 
a step function is used to sync data from Primary Region's EFS Replica to DR region's Studio Domain EFS.
<br />Tip: To extend this codebase for Active-Active DR, just simply add an event trigger for recovery step function
![Active-Active](./assets/SagemakerDomainDrActiveActive.png)

---

## Deployment

### Step 1: Configure constant variables in constants.py file

### Step 2: Bootstrap environment
```
cdk bootstrap
```
### Step 3: Synthesize CDK App
```
cdk synth
```
### Step 4: Deploy Primary Sagemaker Domain
```
cdk deploy SagemakerDomainPrimaryStack
```
### Step 5: Launch Primary Domain's Sagemaker Studio 
Navigate to sagemaker in the primary region, and launch the chosen user's sagemaker studio, then create some test files
### Step 6: Deploy Secondary Sagemaker Domain
```
cdk deploy SagemakerDomainSecondaryStack
```
### Step 7: Deploy Disaster Recovery Step Function
```
cdk deploy ECSTaskStack
```
### Step 8: Execute Disaster Recovery Step Function
Navigate to AWS Step Functions in the secondary region, execute the Disaster Recovery Step Function deployed in step 4
### Step 9: Launch Secondary Domain's Sagemaker Studio 
Navigate to sagemaker in secondary region, and launch the same user's sagemaker studio, you will find your files backed up!


---

## Authors and reviewers

The following people are involved in the design, architecture, development, and testing of this solution:

1. **Jinzhao Feng**, Machine Learning Engineer, Amazon Web Services Inc.
2. **Nick Biso**, Machine Learning Engineer, Amazon Web Services Inc.
3. **Katherine Feng**, Machine Learning Engineer, Amazon Web Services Inc.
4. **Natasha Tchir**, Machine Learning Engineer, Amazon Web Services Inc.

---

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

---

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

