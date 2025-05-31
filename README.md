# OIDC Role Manager

[![CI](https://github.com/YOUR_ORG/oidc-role-manager/workflows/CI/badge.svg)](https://github.com/YOUR_ORG/oidc-role-manager/actions)
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen)](https://github.com/YOUR_ORG/oidc-role-manager)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Enterprise Ready](https://img.shields.io/badge/Enterprise-Ready-green.svg)](#enterprise-deployment-checklist)

Enterprise-grade tool for managing AWS IAM OIDC roles for GitHub Actions using Pulumi.

## 📚 Table of Contents

- [OIDC Role Manager](#oidc-role-manager)
  - [📚 Table of Contents](#-table-of-contents)
  - [🚀 Features](#-features)
  - [📋 Prerequisites](#-prerequisites)
  - [🔧 Installation](#-installation)
  - [🚀 Quick Start](#-quick-start)
  - [📁 Project Structure](#-project-structure)
  - [🎯 Usage](#-usage)
    - [Basic Commands](#basic-commands)
    - [CI/CD Usage](#cicd-usage)
    - [Available Commands](#available-commands)
    - [Deploy Command Options](#deploy-command-options)
  - [📝 Configuration](#-configuration)
    - [Role Directory Structure](#role-directory-structure)
    - [Example Configuration](#example-configuration)
  - [🔧 GitHub Actions Integration](#-github-actions-integration)
  - [🚨 Exit Codes](#-exit-codes)
  - [🔒 Security Best Practices](#-security-best-practices)
  - [🔄 Deployment Workflow](#-deployment-workflow)
    - [Development Workflow](#development-workflow)
    - [Production Workflow](#production-workflow)
  - [🧪 Development](#-development)
    - [Running Tests](#running-tests)
    - [Code Quality](#code-quality)
  - [📚 Troubleshooting](#-troubleshooting)
    - [Common Issues](#common-issues)
    - [Debug Mode](#debug-mode)
    - [Stack Management](#stack-management)
  - [🤝 Contributing](#-contributing)
  - [📄 License](#-license)
  - [🔗 Related](#-related)

## 🚀 Features

- **Enterprise-Ready**: Built with enterprise standards in mind
- **End-to-End Deployment**: Complete automation from configuration to AWS deployment
- **CI/CD Friendly**: Structured JSON output, proper exit codes, and environment variable support
- **Preview Mode**: See changes before applying them
- **Stack Management**: Full Pulumi stack lifecycle management
- **Validation**: Comprehensive configuration validation before deployment
- **Modular Design**: Clean separation of concerns following KISS principles
- **Rich CLI**: Beautiful command-line interface with progress indicators

## 📋 Prerequisites

- Python 3.8+
- **Pulumi CLI**: Installed and configured.
  - See [Pulumi's installation guide](https://www.pulumi.com/docs/install/) and [AWS setup guide](https://www.pulumi.com/docs/clouds/aws/get-started/). You'll need to be logged into Pulumi (e.g., `pulumi login`).
- **AWS CLI**: Installed and configured with appropriate permissions.
  - See the [AWS CLI installation guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) and [configuration guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html).
  - The AWS identity (user or role) running this tool needs permissions to create and manage IAM roles, policies, and OIDC providers. At a minimum, it typically requires permissions similar to `iam:CreateRole`, `iam:DeleteRole`, `iam:GetRole`, `iam:UpdateRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:PutRolePolicy`, `iam:GetRolePolicy`, `iam:DeleteRolePolicy`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:TagRole`, `iam:UntagRole`, and potentially `iam:GetOpenIDConnectProvider` and `iam:CreateOpenIDConnectProvider` if the tool were to manage OIDC providers (though it currently assumes an existing one). For a more secure setup, tailor these permissions precisely.
- **GitHub OIDC Provider in AWS**: This tool manages IAM roles that trust an OIDC identity provider (IdP) for GitHub Actions. You must have already configured this OIDC IdP in each target AWS account.
  - Refer to the official AWS documentation: [Creating OpenID Connect (OIDC) identity providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html).
  - And GitHub's documentation: [About security hardening with OpenID Connect](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect).

## 🔧 Installation

```bash
# Clone the repository
git clone https://github.com/AgentGino/oidc-role-manager.git 
cd oidc-role-manager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development
pip install -e ".[dev]"
```

## 🚀 Quick Start

This guide will walk you through deploying your first OIDC role using this tool.

1.  **Ensure Prerequisites**: Double-check that all items in the [Prerequisites](#-prerequisites) section are met.

2.  **Install the Tool**: Follow the [Installation](#-installation) instructions above.

3.  **Initialize Pulumi Stack (if not already done)**:
    This tool uses Pulumi stacks to manage resources per AWS account. If you haven't used Pulumi for this AWS account before with this project, you'll need to initialize a stack. The default stack name is `dev`, but you can choose another one.

    The `cli.py` tool will typically create a stack for you if it doesn't exist, based on the account ID (e.g., `dev-123456789012`). However, you might want to create a specific stack or set a default one.

    ```bash
    # Ensure Pulumi.yaml exists (it should be in the cloned repo)
    # Initialize a new stack (e.g., for account 123456789012)
    pulumi stack init dev-123456789012

    # Set AWS region for this stack (replace us-west-2 as needed)
    pulumi config set aws:region us-west-2
    ```
    *Note: The `cli.py` script will also try to create a stack like `dev-{account-id}` if one doesn't exist, and prompt for a region if `aws:region` is not set.* 

4.  **Configure Your First Role**:
    Role configurations are stored in the `roles/` directory (which is gitignored by default to protect sensitive configurations).

    *   Create the directory structure:
        ```bash
        mkdir -p roles/123456789012/MyFirstRole # Replace 123456789012 with your AWS Account ID
        ```

    *   Create `roles/123456789012/MyFirstRole/details.json` with content like this (adjust `your-org/your-repo` and other details):
        ```json
        {
          "roleName": "GitHubActionMyFirstRole",
          "description": "My first OIDC role managed by oidc-role-manager",
          "oidcProviderUrl": "token.actions.githubusercontent.com", // This usually stays the same
          "githubSubjectClaim": "repo:your-org/your-repo:ref:refs/heads/main", // Adjust to your repo and branch/tag/environment
          "audience": "sts.amazonaws.com", // This usually stays the same
          "tags": {
            "ManagedBy": "OidcRoleManager",
            "Repository": "your-org/your-repo"
          }
        }
        ```

    *   (Optional) Add managed policies. Create `roles/123456789012/MyFirstRole/managed-policies.json`:
        ```json
        [
          "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
        ]
        ```

    *   (Optional) Add an inline policy. Create `roles/123456789012/MyFirstRole/inline-CustomAccess.json`:
        ```json
        {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Action": "s3:ListBucket",
              "Resource": "arn:aws:s3:::your-specific-bucket"
            }
          ]
        }
        ```

5.  **Validate Configuration**:
    ```bash
    python cli.py validate --account-id 123456789012
    ```
    If there are errors, the tool will report them. Fix them and re-run.

6.  **Preview Deployment (Dry Run)**:
    This shows you what resources Pulumi will create or modify without actually making changes.
    ```bash
    python cli.py deploy --account-id 123456789012 --dry-run
    ```
    Review the output carefully.

7.  **Deploy Your Role**:
    ```bash
    python cli.py deploy --account-id 123456789012
    ```
    You will be prompted by Pulumi to confirm the changes unless you use `--auto-approve`.

8.  **Check Status**:
    After deployment, you can check the status and outputs:
    ```bash
    python cli.py status --account-id 123456789012
    ```

Congratulations! You've deployed your first OIDC role. You can now use this role in your GitHub Actions workflows by specifying its ARN in the `role-to-assume` field of the `aws-actions/configure-aws-credentials` action.

Remember to replace `yourorg`, `your-repo`, and `123456789012` with your actual GitHub organization/username, repository name, and AWS account ID throughout these examples.

## 📁 Project Structure

```
oidc-role-manager/
├── cli.py                      # Main CLI application entry point
├── oidc_role_manager/          # Core package
│   ├── __init__.py
│   ├── config_loader.py        # Configuration loading and validation
│   ├── iam_resources.py        # AWS IAM resource management
│   ├── pulumi_manager.py       # Pulumi automation API integration
│   └── constants.py            # Global constants and definitions
├── tests/                      # Comprehensive test suite
│   ├── __init__.py
│   ├── test_cli.py             # CLI functionality tests
│   ├── test_config_loader.py   # Configuration loading tests
│   ├── test_iam_resources.py   # IAM resource tests
│   ├── test_pulumi_manager.py  # Pulumi integration tests
│   └── test_constants.py       # Constants and utilities tests
├── roles/                      # Role configurations (gitignored for security)
│   ├── .gitkeep               # Keeps directory in version control
│   └── examples/              # Example configurations for reference
│       └── 123456789012/      # Example account structure
├── .github/                   # GitHub Actions workflows and templates
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── pyproject.toml            # Project configuration and build settings
├── setup.py                  # Package setup configuration
├── Pulumi.yaml               # Pulumi project configuration
├── Pulumi.dev*.yaml          # Pulumi stack configurations
├── .gitignore               # Git ignore patterns
├── .pre-commit-config.yaml  # Pre-commit hooks configuration
├── LICENSE                  # MIT license
├── README.md               # This file
├── ENTERPRISE_CHECKLIST.md # Enterprise deployment checklist
└── check_coverage.py       # Coverage validation script
```

## 🎯 Usage

### Basic Commands

```bash
# Preview deployment (dry-run)
python cli.py deploy --account-id 123456789012 --dry-run

# Deploy all roles for an account
python cli.py deploy --account-id 123456789012

# Deploy specific role
python cli.py deploy --account-id 123456789012 --role-name DeployToStaging

# Check deployment status
python cli.py status --account-id 123456789012

# Validate configurations
python cli.py validate

# Destroy all resources
python cli.py destroy --account-id 123456789012

# Get help
python cli.py --help
```

### CI/CD Usage

```bash
# Environment variables for CI/CD
export AWS_ACCOUNT_ID="123456789012"
export AWS_REGION="us-west-2"
export OIDC_JSON_OUTPUT="true"
export OIDC_LOG_LEVEL="INFO"
export OIDC_AUTO_APPROVE="true"

# Preview with JSON output
python cli.py deploy --account-id $AWS_ACCOUNT_ID --dry-run

# Deploy with auto-approval
python cli.py deploy --account-id $AWS_ACCOUNT_ID --auto-approve
```

### Available Commands

| Command | Description |
|---------|-------------|
| `deploy` | Deploy or preview OIDC roles |
| `destroy` | Destroy all deployed resources |
| `status` | Show deployment status and outputs |
| `validate` | Validate configurations without deploying |

### Deploy Command Options

| Option | Environment Variable | Description |
|--------|---------------------|-------------|
| `--account-id` | `AWS_ACCOUNT_ID` | Target AWS Account ID |
| `--role-name` | `OIDC_ROLE_NAME` | Specific role to process |
| `--roles-dir` | `OIDC_ROLES_DIR` | Directory containing role definitions |
| `--aws-region` | `AWS_REGION` | AWS region for resources |
| `--aws-profile` | `AWS_PROFILE` | AWS profile to use |
| `--stack-name` | `PULUMI_STACK_NAME` | Pulumi stack name (default: dev) |
| `--log-level` | `OIDC_LOG_LEVEL` | Logging level |
| `--json-output` | `OIDC_JSON_OUTPUT` | Enable JSON output for CI/CD |
| `--dry-run` | - | Preview changes without applying |
| `--auto-approve` | `OIDC_AUTO_APPROVE` | Auto-approve deployment |

## 📝 Configuration

### Role Directory Structure

```
roles/
└── {account-id}/
    └── {role-name}/
        ├── details.json              # Role configuration
        ├── managed-policies.json     # AWS managed policies (optional)
        └── inline-{name}.json       # Inline policies (optional)
```

### Example Configuration

**`roles/123456789012/DeployToStaging/details.json`**
```json
{
  "roleName": "GitHubActionDeployToStaging",
  "description": "Role for GitHub Actions to deploy to staging",
  "oidcProviderUrl": "token.actions.githubusercontent.com",
  "githubSubjectClaim": "repo:your-org/your-repo:environment:staging",
  "audience": "sts.amazonaws.com",
  "tags": {
    "Application": "WebApp",
    "Environment": "Staging",
    "AutomationTool": "GitHubActions"
  }
}
```

**`roles/123456789012/DeployToStaging/managed-policies.json`**
```json
[
  "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
  "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
]
```

**`roles/123456789012/DeployToStaging/inline-CustomPolicy.json`**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::my-deployment-bucket/*"
    }
  ]
}
```

## 🔧 GitHub Actions Integration

```yaml
name: Deploy Infrastructure

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/GitHubActionDeployToStaging
          aws-region: ${{ vars.AWS_REGION }}
      
      - name: Validate configurations
        run: |
          python cli.py validate
      
      - name: Preview deployment
        run: |
          python cli.py deploy \
            --account-id ${{ vars.AWS_ACCOUNT_ID }} \
            --aws-region ${{ vars.AWS_REGION }} \
            --dry-run \
            --json-output
      
      - name: Deploy OIDC roles
        run: |
          python cli.py deploy \
            --account-id ${{ vars.AWS_ACCOUNT_ID }} \
            --aws-region ${{ vars.AWS_REGION }} \
            --auto-approve \
            --json-output
```

## 🚨 Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Validation error |
| 4 | AWS error |

## 🔒 Security Best Practices

1. **Never commit actual role configurations** - Use the examples directory for templates
2. **Use least privilege** - Only grant necessary permissions
3. **Validate all configurations** - Always run `validate` before deployment
4. **Preview before deploying** - Use `--dry-run` to see changes first
5. **Monitor role usage** - Set up CloudTrail logging
6. **Rotate credentials** - Regularly review and update access patterns

## 🔄 Deployment Workflow

### Development Workflow
```bash
# 1. Validate configurations
python cli.py validate

# 2. Preview changes
python cli.py deploy --account-id 123456789012 --dry-run

# 3. Deploy with confirmation
python cli.py deploy --account-id 123456789012

# 4. Check status
python cli.py status --account-id 123456789012

# 5. View outputs
python cli.py status --account-id 123456789012 --json-output
```

### Production Workflow
```bash
# Automated CI/CD deployment
python cli.py deploy \
  --account-id $AWS_ACCOUNT_ID \
  --aws-region $AWS_REGION \
  --auto-approve \
  --json-output
```

## 🧪 Development

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=oidc_role_manager
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

## 📚 Troubleshooting

### Common Issues

1. **Invalid Account ID**: Ensure account ID is exactly 12 digits
2. **Missing OIDC Provider**: GitHub OIDC provider must exist in target account
3. **Permission Denied**: Ensure AWS credentials have IAM permissions
4. **Configuration Errors**: Use `validate` command to check configurations
5. **Stack Already Exists**: Use different `--stack-name` or destroy existing stack

### Debug Mode

```bash
# Enable debug logging
python cli.py --log-level DEBUG deploy --account-id 123456789012 --dry-run
```

### Stack Management

```bash
# Check stack status
python cli.py status --stack-name production --account-id 123456789012

# Use different stack
python cli.py deploy --account-id 123456789012 --stack-name production

# Destroy stack
python cli.py destroy --stack-name production --account-id 123456789012
```

## 🤝 Contributing

1. Follow the KISS principle - keep it simple and modular
2. Add tests for new functionality
3. Update documentation
4. Follow existing code style

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related

- [Pulumi AWS Provider](https://www.pulumi.com/registry/packages/aws/)
- [Pulumi Automation API](https://www.pulumi.com/docs/guides/automation-api/)
- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [AWS IAM OIDC Provider](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
