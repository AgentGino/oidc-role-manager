# Cross-Account Authentication Guide

This document provides detailed information about cross-account authentication patterns supported by the OIDC Role Manager.

## Overview

Cross-account authentication allows you to deploy OIDC roles to multiple AWS accounts from a central deployment process. This is essential for enterprise environments where you need to manage resources across development, staging, and production accounts.

## Authentication Methods

### 1. AWS Profile-Based Authentication

**Use Case**: Simple multi-account setups with local credentials
**Security Level**: Medium
**Complexity**: Low

```bash
# Configure profiles in ~/.aws/config
[profile account-dev]
region = us-west-2
role_arn = arn:aws:iam::123456789012:role/AdminRole
source_profile = default

[profile account-prod]
region = us-west-2
role_arn = arn:aws:iam::987654321098:role/AdminRole
source_profile = default

# Deploy using profiles
python cli.py deploy --account-id 123456789012 --aws-profile account-dev
python cli.py deploy --account-id 987654321098 --aws-profile account-prod
```

### 2. Cross-Account Role Assumption

**Use Case**: Enterprise deployments with centralized authentication
**Security Level**: High
**Complexity**: Medium

```bash
# Deploy with cross-account role assumption
python cli.py deploy \
  --account-id 123456789012 \
  --assume-role-arn "arn:aws:iam::123456789012:role/CrossAccountDeploymentRole" \
  --external-id "unique-external-id"
```

### 3. GitHub Actions OIDC

**Use Case**: CI/CD pipeline deployments
**Security Level**: High
**Complexity**: Medium

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::CENTRAL-ACCOUNT:role/GitHubOIDCDeploymentRole
    aws-region: us-west-2

- name: Deploy to target account
  run: |
    python cli.py deploy \
      --account-id ${{ vars.TARGET_ACCOUNT_ID }} \
      --assume-role-arn "arn:aws:iam::${{ vars.TARGET_ACCOUNT_ID }}:role/CrossAccountDeploymentRole"
```

### 4. AWS SSO/Identity Center Integration

**Use Case**: Organizations using AWS SSO
**Security Level**: High
**Complexity**: Low

```bash
# Login with SSO
aws sso login --profile sso-admin

# Deploy using SSO profile
python cli.py deploy --account-id 123456789012 --aws-profile sso-admin
```

## Implementation Details

### Pulumi AWS Provider Configuration

The tool configures the Pulumi AWS provider with cross-account capabilities:

```python
# Enhanced provider configuration
provider_opts = {"region": self.aws_region}
if self.aws_profile:
    provider_opts["profile"] = self.aws_profile

# Cross-account role assumption
if self.assume_role_arn:
    assume_role_config = {
        "role_arn": self.assume_role_arn,
        "session_name": f"oidc-role-manager-{self.stack_name}"
    }
    if self.external_id:
        assume_role_config["external_id"] = self.external_id
    
    provider_opts["assume_role"] = assume_role_config

aws_provider = aws.Provider("aws-provider", **provider_opts)
```

### CLI Parameters

| Parameter | Environment Variable | Description |
|-----------|---------------------|-------------|
| `--assume-role-arn` | `AWS_ASSUME_ROLE_ARN` | ARN of role to assume for cross-account access |
| `--external-id` | `AWS_EXTERNAL_ID` | External ID for additional security |
| `--aws-profile` | `AWS_PROFILE` | AWS profile for authentication |
| `--aws-region` | `AWS_REGION` | AWS region for resources |

## Security Considerations

### External ID Usage

External IDs provide additional security for cross-account role assumption:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::CENTRAL-ACCOUNT:role/DeploymentRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "unique-external-id-per-account"
        }
      }
    }
  ]
}
```

### Trust Policy Best Practices

1. **Use specific principal ARNs** instead of wildcards
2. **Include external ID conditions** for additional security
3. **Limit session duration** with `MaxSessionDuration`
4. **Add IP address restrictions** if possible

Example trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::CENTRAL-ACCOUNT:role/GitHubOIDCDeploymentRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "${aws:username}-deployment"
        },
        "DateGreaterThan": {
          "aws:CurrentTime": "2024-01-01T00:00:00Z"
        },
        "DateLessThan": {
          "aws:CurrentTime": "2025-01-01T00:00:00Z"
        }
      }
    }
  ]
}
```

### Required IAM Permissions

The deployment role needs these permissions in target accounts:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:UpdateRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:GetRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:TagRole",
        "iam:UntagRole"
      ],
      "Resource": [
        "arn:aws:iam::*:role/GitHubAction*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetOpenIDConnectProvider"
      ],
      "Resource": [
        "arn:aws:iam::*:oidc-provider/token.actions.githubusercontent.com"
      ]
    }
  ]
}
```

## Enterprise Deployment Pattern

### Hub and Spoke Model

1. **Central Hub Account**: Contains the deployment pipeline and central roles
2. **Spoke Accounts**: Target accounts for OIDC role deployment

```
┌─────────────────┐     assume     ┌─────────────────┐
│   Hub Account   │ ────────────► │ Development     │
│                 │               │ Account         │
│ GitHub Actions  │               │ 123456789012    │
│ Central Pipeline│               └─────────────────┘
│                 │     assume     ┌─────────────────┐
│                 │ ────────────► │ Staging Account │
│                 │               │ 987654321098    │
│                 │               └─────────────────┘
│                 │     assume     ┌─────────────────┐
│                 │ ────────────► │ Production      │
│                 │               │ Account         │
│                 │               │ 555666777888    │
└─────────────────┘               └─────────────────┘
```

### Account Setup Workflow

1. **Central Hub Account Setup**:
   - Create GitHub OIDC provider
   - Create central deployment role
   - Configure GitHub repository variables

2. **Target Account Setup** (for each spoke account):
   - Create cross-account deployment role
   - Configure trust relationship to hub account
   - Set up unique external ID
   - Create GitHub OIDC provider in target account

3. **Repository Configuration**:
   - Set up GitHub environments
   - Configure account-specific variables
   - Add deployment workflows

### Automated Multi-Account Deployment

Use the provided deployment script for automated multi-account deployment:

```bash
# Configure accounts in the script
ACCOUNTS=(
    "123456789012:dev-profile:dev-role"
    "987654321098:staging-profile:staging-role"
    "555666777888:prod-profile:prod-role"
)

# Deploy to all accounts using role assumption
AWS_EXTERNAL_ID="my-org-deployment" \
./scripts/cross-account-deploy.sh assume-role
```

## Troubleshooting

### Common Issues

1. **Access Denied Errors**
   - Verify trust relationships
   - Check external ID configuration
   - Ensure role has necessary permissions

2. **Invalid Role ARN**
   - Verify account ID format
   - Check role name spelling
   - Ensure role exists in target account

3. **External ID Mismatch**
   - Verify external ID in trust policy
   - Check environment variable setting
   - Ensure consistency across deployments

### Debug Commands

```bash
# Test role assumption
aws sts assume-role \
  --role-arn "arn:aws:iam::123456789012:role/CrossAccountDeploymentRole" \
  --role-session-name "test-session" \
  --external-id "my-external-id"

# Debug deployment with verbose logging
python cli.py --log-level DEBUG deploy \
  --account-id 123456789012 \
  --assume-role-arn "arn:aws:iam::123456789012:role/TestRole" \
  --external-id "test-id" \
  --dry-run
```

## Best Practices

1. **Use unique external IDs** for each target account
2. **Implement least privilege** access in cross-account roles
3. **Monitor cross-account activities** with CloudTrail
4. **Rotate external IDs** periodically
5. **Use separate roles** for different environments
6. **Document trust relationships** clearly
7. **Test role assumption** before deployment
8. **Implement automated verification** of cross-account setup

## Migration Guide

### From Manual to Automated

1. **Audit existing OIDC roles** across all accounts
2. **Document current configurations** and permissions
3. **Set up cross-account roles** in target accounts
4. **Test deployment pipeline** in development first
5. **Migrate configurations** to the tool format
6. **Deploy using automation** and verify functionality
7. **Decommission manual processes** after validation

### From Profile-Based to Role Assumption

1. **Create cross-account deployment roles**
2. **Configure trust relationships**
3. **Update deployment scripts** to use role assumption
4. **Test new authentication method**
5. **Remove profile dependencies**
6. **Update documentation** and runbooks 