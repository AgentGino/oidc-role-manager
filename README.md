# OIDC Role Manager

Enterprise-grade tool for managing AWS IAM OIDC roles for GitHub Actions using Pulumi.

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
- Pulumi CLI installed and configured
- AWS CLI configured with appropriate permissions
- GitHub OIDC provider already configured in target AWS accounts

## 🔧 Installation

```bash
# Clone the repository
git clone <repository-url>
cd oidc-role-manager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development
pip install -e ".[dev]"
```

## 📁 Project Structure

```
oidc-role-manager/
├── cli.py                   # Main CLI application
├── oidc_role_manager/       # Core package
│   ├── __init__.py
│   ├── config_loader.py     # Configuration loading and validation
│   ├── iam_resources.py     # AWS IAM resource management
│   ├── pulumi_manager.py    # Pulumi automation API integration
│   └── constants.py         # Global constants
├── tests/                   # Test suite
│   ├── __init__.py
│   └── test_config_loader.py
├── roles/                   # Role configurations (gitignored)
│   └── examples/           # Example configurations
├── requirements.txt        # Python dependencies
├── requirements-dev.txt    # Development dependencies
├── pyproject.toml         # Project configuration
├── setup.py               # Setup script
└── Pulumi.yaml            # Pulumi project configuration
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

[Add your license here]

## 🔗 Related

- [Pulumi AWS Provider](https://www.pulumi.com/registry/packages/aws/)
- [Pulumi Automation API](https://www.pulumi.com/docs/guides/automation-api/)
- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [AWS IAM OIDC Provider](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) 