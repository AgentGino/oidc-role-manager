"""
Enterprise OIDC Role Manager Constants
Global configuration constants for the application
"""

# Default tags applied to all IAM resources
DEFAULT_TAGS = {
    "ManagedBy": "OIDC-Role-Manager",
    "Environment": "Development",  # Can be overridden in role configs
    "Tool": "Pulumi",
    "Purpose": "OIDC-GitHub-Integration"
}

# OIDC Configuration
DEFAULT_AUDIENCE = "sts.amazonaws.com"
GITHUB_OIDC_PROVIDER_URL = "token.actions.githubusercontent.com"

# AWS Resource Configuration
MAX_INLINE_POLICIES_PER_ROLE = 10
MAX_MANAGED_POLICIES_PER_ROLE = 20

# Validation Settings
VALID_ENVIRONMENTS = ["Development", "Staging", "Production", "Test"]
REQUIRED_ROLE_FIELDS = ["roleName", "oidcProviderUrl", "githubSubjectClaim"]

# Enterprise naming patterns (examples)
ENTERPRISE_NAMING_PATTERNS = {
    "role_prefix": "GHA",  # GitHub Actions
    "environment_tags": ["Dev", "Staging", "Prod", "Test"],
    "max_role_name_length": 64
}

# You can add other constants here, e.g.:
# TRUSTED_OIDC_ISSUER_URLS = [
# "oidc.eks.us-west-2.amazonaws.com/id/YOUR_CLUSTER_ID_1",
# "oidc.eks.eu-central-1.amazonaws.com/id/YOUR_CLUSTER_ID_2"
# ] 