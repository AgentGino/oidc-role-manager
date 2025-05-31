import pulumi
import pulumi_aws as aws
import json
import logging
from oidc_role_manager.config_loader import RoleConfig
from . import constants

logger = logging.getLogger(__name__)

def _construct_github_oidc_provider_details(account_id: str, oidc_url_from_config: str) -> tuple[str, str]:
    """Parses OIDC URL and constructs the OIDC provider ARN and URL without scheme."""
    if oidc_url_from_config.startswith("https://"):
        oidc_url_no_scheme = oidc_url_from_config[len("https://"):]
    else:
        oidc_url_no_scheme = oidc_url_from_config
    
    # IMPORTANT: The OIDC provider (e.g., for token.actions.githubusercontent.com)
    # must already exist in the target AWS account (account_id).
    oidc_provider_arn = f"arn:aws:iam::{account_id}:oidc-provider/{oidc_url_no_scheme}"
    logger.debug(f"Constructed OIDC provider ARN: {oidc_provider_arn}")
    return oidc_provider_arn, oidc_url_no_scheme

def _generate_github_assume_role_policy(oidc_provider_arn: str, oidc_url_no_scheme: str, 
                                      subject_claim: str, audience: str) -> str:
    """Generates the JSON string for the IAM role's assume role policy document for GitHub OIDC."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": oidc_provider_arn
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        f"{oidc_url_no_scheme}:sub": subject_claim,
                        f"{oidc_url_no_scheme}:aud": audience
                    }
                }
            }
        ]
    }
    logger.debug(f"Generated assume role policy document for OIDC provider ARN: {oidc_provider_arn}")
    return json.dumps(policy)

def _prepare_tags(config: RoleConfig) -> dict:
    """Merges default tags with role-specific tags and adds traceability tags."""
    current_tags = constants.DEFAULT_TAGS.copy()
    if 'tags' in config.details and isinstance(config.details['tags'], dict):
        current_tags.update(config.details['tags'])
    current_tags["ConfigPath"] = config.path
    current_tags["AccountId"] = config.account_id
    logger.debug(f"Prepared tags for role {config.role_name}: {current_tags}")
    return current_tags

def _create_iam_role(pulumi_resource_name: str, role_name: str, description: str | None,
                     assume_role_policy_doc: str, tags: dict, 
                     opts: pulumi.ResourceOptions | None) -> aws.iam.Role:
    """Creates the core aws.iam.Role Pulumi resource."""
    iam_role = aws.iam.Role(pulumi_resource_name,
                            name=role_name,
                            description=description,
                            assume_role_policy=assume_role_policy_doc,
                            tags=tags,
                            opts=opts)
    logger.info(f"Defined aws.iam.Role: {role_name} (Pulumi name: {pulumi_resource_name})")
    return iam_role

def _attach_managed_policies(pulumi_resource_name_prefix: str, role_name_for_log: str, 
                             managed_policy_arns: list[str], iam_role_name: pulumi.Output[str],
                             opts: pulumi.ResourceOptions | None):
    """Attaches managed policies to the IAM role."""
    if not managed_policy_arns:
        logger.debug(f"No managed policies to attach for role {role_name_for_log}.")
        return
    for i, policy_arn in enumerate(managed_policy_arns):
        pulumi_attachment_name = f"{pulumi_resource_name_prefix}-managed-{i}"
        aws.iam.RolePolicyAttachment(pulumi_attachment_name,
                                     role=iam_role_name,
                                     policy_arn=policy_arn,
                                     opts=opts)
        logger.debug(f"Attaching managed policy {policy_arn} to role {role_name_for_log} (Pulumi name: {pulumi_attachment_name})")

def _attach_inline_policies(pulumi_resource_name_prefix: str, role_name_for_log: str, 
                            inline_policies_map: dict, iam_role_name: pulumi.Output[str],
                            opts: pulumi.ResourceOptions | None):
    """Attaches inline policies to the IAM role."""
    if not inline_policies_map:
        logger.debug(f"No inline policies to attach for role {role_name_for_log}.")
        return
    for policy_file_name, policy_doc in inline_policies_map.items():
        # Extract a cleaner policy name from filename like inline-CloudWatchLogs.json -> CloudWatchLogs
        cleaned_policy_name_from_file = policy_file_name.replace("inline-", "", 1).replace(".json", "")
        
        # Construct the AWS Inline Policy Name as {rolename}-{cleaned_policy_name}
        aws_inline_policy_name = f"{role_name_for_log}-{cleaned_policy_name_from_file}"

        # Pulumi resource name needs to be unique within the stack
        pulumi_policy_resource_name = f"{pulumi_resource_name_prefix}-inline-{cleaned_policy_name_from_file}"
        
        aws.iam.RolePolicy(pulumi_policy_resource_name,
                           role=iam_role_name,
                           name=aws_inline_policy_name, # Actual AWS Inline Policy Name
                           policy=json.dumps(policy_doc),
                           opts=opts)
        logger.debug(f"Attaching inline policy '{aws_inline_policy_name}' to role {role_name_for_log} (Pulumi name: {pulumi_policy_resource_name})")

def _safe_export(key: str, value: pulumi.Output) -> None:
    """Safely export a value, only if we're in a valid Pulumi stack context."""
    try:
        pulumi.export(key, value)
        logger.debug(f"Exported: {key}")
    except Exception as e:
        # This happens when not running in a Pulumi stack context (e.g., CLI validation)
        logger.debug(f"Skipping export '{key}' - not in Pulumi stack context: {e}")

def create_iam_role_for_github_oidc(config: RoleConfig, pulumi_provider: aws.Provider = None):
    """
    Creates an IAM OIDC role for GitHub Actions based on the provided RoleConfig.
    Orchestrates calls to helper functions for modularity.
    Optionally uses a specific Pulumi AWS provider.
    """
    logger.info(f"--- Defining IAM resources for role: {config.role_name} in account {config.account_id} ---")

    aws_role_name = config.role_name
    # Pulumi resource names should be unique across the entire stack deployment.
    # Prefixing with account_id and the role_name (from config) ensures this.
    pulumi_resource_name_base = f"{config.account_id}-{aws_role_name}"

    oidc_provider_arn, oidc_url_no_scheme = _construct_github_oidc_provider_details(
        config.account_id, 
        config.details['oidcProviderUrl']
    )

    assume_role_policy_doc = _generate_github_assume_role_policy(
        oidc_provider_arn,
        oidc_url_no_scheme,
        config.details['githubSubjectClaim'],
        config.details.get('audience', 'sts.amazonaws.com')
    )

    tags = _prepare_tags(config)
    
    opts = pulumi.ResourceOptions(provider=pulumi_provider) if pulumi_provider else None

    iam_role = _create_iam_role(
        pulumi_resource_name=f"{pulumi_resource_name_base}-role",
        role_name=aws_role_name,
        description=config.details.get('description'),
        assume_role_policy_doc=assume_role_policy_doc,
        tags=tags,
        opts=opts
    )

    _attach_managed_policies(
        pulumi_resource_name_prefix=pulumi_resource_name_base,
        role_name_for_log=aws_role_name,
        managed_policy_arns=config.managed_policies,
        iam_role_name=iam_role.name, # Pass the Output[str] name
        opts=opts
    )

    _attach_inline_policies(
        pulumi_resource_name_prefix=pulumi_resource_name_base,
        role_name_for_log=aws_role_name,
        inline_policies_map=config.inline_policies,
        iam_role_name=iam_role.name, # Pass the Output[str] name
        opts=opts
    )

    # Safe exports - only export when in a valid Pulumi stack context
    _safe_export(f"{pulumi_resource_name_base}_role_arn", iam_role.arn)
    _safe_export(f"{pulumi_resource_name_base}_role_name", iam_role.name)
    
    logger.info(f"--- Successfully defined all IAM resources for role: {aws_role_name} ---")
    return iam_role 