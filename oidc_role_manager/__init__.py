"""
OIDC Role Manager - Enterprise-grade AWS IAM OIDC roles management

This package provides tools for managing AWS IAM OIDC roles for GitHub Actions
using Pulumi Infrastructure as Code.
"""

__version__ = "1.0.0"
__author__ = "DevOps Team"
__email__ = "devops@yourorg.com"

# Core components
from . import config_loader
from . import iam_resources
from . import pulumi_manager
from . import constants

__all__ = [
    "config_loader",
    "iam_resources", 
    "pulumi_manager",
    "constants",
] 