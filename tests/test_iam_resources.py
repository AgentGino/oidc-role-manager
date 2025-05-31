"""
Tests for iam_resources module
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call

from oidc_role_manager.config_loader import RoleConfig
from oidc_role_manager import iam_resources, constants


class TestConstructGithubOidcProviderDetails:
    """Test cases for _construct_github_oidc_provider_details function."""
    
    def test_construct_github_oidc_provider_details_with_https(self):
        """Test construction with https URL."""
        account_id = "123456789012"
        oidc_url = "https://token.actions.githubusercontent.com"
        
        arn, url_no_scheme = iam_resources._construct_github_oidc_provider_details(
            account_id, oidc_url
        )
        
        expected_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
        assert arn == expected_arn
        assert url_no_scheme == "token.actions.githubusercontent.com"
    
    def test_construct_github_oidc_provider_details_without_https(self):
        """Test construction without https scheme."""
        account_id = "123456789012"
        oidc_url = "token.actions.githubusercontent.com"
        
        arn, url_no_scheme = iam_resources._construct_github_oidc_provider_details(
            account_id, oidc_url
        )
        
        expected_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
        assert arn == expected_arn
        assert url_no_scheme == "token.actions.githubusercontent.com"


class TestGenerateGithubAssumeRolePolicy:
    """Test cases for _generate_github_assume_role_policy function."""
    
    def test_generate_github_assume_role_policy(self):
        """Test assume role policy generation."""
        oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
        oidc_url_no_scheme = "token.actions.githubusercontent.com"
        subject_claim = "repo:org/repo:environment:production"
        audience = "sts.amazonaws.com"
        
        policy_json = iam_resources._generate_github_assume_role_policy(
            oidc_provider_arn, oidc_url_no_scheme, subject_claim, audience
        )
        
        policy = json.loads(policy_json)
        
        assert policy["Version"] == "2012-10-17"
        assert len(policy["Statement"]) == 1
        
        statement = policy["Statement"][0]
        assert statement["Effect"] == "Allow"
        assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
        assert statement["Principal"]["Federated"] == oidc_provider_arn
        
        conditions = statement["Condition"]["StringEquals"]
        assert conditions[f"{oidc_url_no_scheme}:sub"] == subject_claim
        assert conditions[f"{oidc_url_no_scheme}:aud"] == audience


class TestPrepareTags:
    """Test cases for _prepare_tags function."""
    
    def test_prepare_tags_with_default_only(self):
        """Test tag preparation with only default tags."""
        config = RoleConfig(
            account_id="123456789012",
            role_name_dir="TestRole",
            details={
                "roleName": "TestRole",
                "oidcProviderUrl": "token.actions.githubusercontent.com",
                "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
            },
            managed_policies=[],
            inline_policies={},
            base_dir="/base"
        )
        
        tags = iam_resources._prepare_tags(config)
        
        # Should include default tags plus computed ones
        expected_tags = constants.DEFAULT_TAGS.copy()
        expected_tags["ConfigPath"] = config.path
        expected_tags["AccountId"] = config.account_id
        
        assert tags == expected_tags
    
    def test_prepare_tags_with_custom_tags(self):
        """Test tag preparation with custom tags."""
        config = RoleConfig(
            account_id="123456789012",
            role_name_dir="TestRole",
            details={
                "roleName": "TestRole",
                "oidcProviderUrl": "token.actions.githubusercontent.com",
                "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main",
                "tags": {
                    "Environment": "Production",  # Override default
                    "Application": "WebApp",      # New tag
                    "Team": "DevOps"             # New tag
                }
            },
            managed_policies=[],
            inline_policies={},
            base_dir="/base"
        )
        
        tags = iam_resources._prepare_tags(config)
        
        # Should include merged tags
        assert tags["Environment"] == "Production"  # Overridden
        assert tags["Application"] == "WebApp"      # Added
        assert tags["Team"] == "DevOps"            # Added
        assert tags["ManagedBy"] == constants.DEFAULT_TAGS["ManagedBy"]  # From default
        assert tags["ConfigPath"] == config.path
        assert tags["AccountId"] == config.account_id
    
    def test_prepare_tags_invalid_tags_ignored(self):
        """Test that invalid tags structure is ignored."""
        config = RoleConfig(
            account_id="123456789012",
            role_name_dir="TestRole",
            details={
                "roleName": "TestRole",
                "oidcProviderUrl": "token.actions.githubusercontent.com",
                "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main",
                "tags": "invalid_tags_string"  # Invalid: should be dict
            },
            managed_policies=[],
            inline_policies={},
            base_dir="/base"
        )
        
        tags = iam_resources._prepare_tags(config)
        
        # Should only include default tags plus computed ones
        expected_tags = constants.DEFAULT_TAGS.copy()
        expected_tags["ConfigPath"] = config.path
        expected_tags["AccountId"] = config.account_id
        
        assert tags == expected_tags


@patch('oidc_role_manager.iam_resources.aws.iam.Role')
class TestCreateIamRole:
    """Test cases for _create_iam_role function."""
    
    def test_create_iam_role_success(self, mock_role_class):
        """Test successful IAM role creation."""
        mock_role = MagicMock()
        mock_role_class.return_value = mock_role
        
        result = iam_resources._create_iam_role(
            pulumi_resource_name="test-role",
            role_name="TestRole",
            description="Test role description",
            assume_role_policy_doc='{"Version": "2012-10-17"}',
            tags={"Environment": "test"},
            opts=None
        )
        
        # Verify role was created with correct parameters
        mock_role_class.assert_called_once_with(
            "test-role",
            name="TestRole",
            description="Test role description",
            assume_role_policy='{"Version": "2012-10-17"}',
            tags={"Environment": "test"},
            opts=None
        )
        
        assert result == mock_role
    
    def test_create_iam_role_with_opts(self, mock_role_class):
        """Test IAM role creation with Pulumi options."""
        mock_role = MagicMock()
        mock_role_class.return_value = mock_role
        mock_opts = MagicMock()
        
        result = iam_resources._create_iam_role(
            pulumi_resource_name="test-role",
            role_name="TestRole",
            description=None,
            assume_role_policy_doc='{"Version": "2012-10-17"}',
            tags={},
            opts=mock_opts
        )
        
        mock_role_class.assert_called_once_with(
            "test-role",
            name="TestRole",
            description=None,
            assume_role_policy='{"Version": "2012-10-17"}',
            tags={},
            opts=mock_opts
        )


@patch('oidc_role_manager.iam_resources.aws.iam.RolePolicyAttachment')
class TestAttachManagedPolicies:
    """Test cases for _attach_managed_policies function."""
    
    def test_attach_managed_policies_success(self, mock_attachment_class):
        """Test successful managed policy attachment."""
        mock_role_name = MagicMock()
        managed_policies = [
            "arn:aws:iam::aws:policy/ReadOnlyAccess",
            "arn:aws:iam::aws:policy/PowerUserAccess"
        ]
        
        iam_resources._attach_managed_policies(
            pulumi_resource_name_prefix="test",
            role_name_for_log="TestRole",
            managed_policy_arns=managed_policies,
            iam_role_name=mock_role_name,
            opts=None
        )
        
        # Should create two policy attachments
        assert mock_attachment_class.call_count == 2
        
        calls = mock_attachment_class.call_args_list
        assert calls[0] == call(
            "test-managed-0",
            role=mock_role_name,
            policy_arn="arn:aws:iam::aws:policy/ReadOnlyAccess",
            opts=None
        )
        assert calls[1] == call(
            "test-managed-1",
            role=mock_role_name,
            policy_arn="arn:aws:iam::aws:policy/PowerUserAccess",
            opts=None
        )
    
    def test_attach_managed_policies_empty_list(self, mock_attachment_class):
        """Test with empty managed policies list."""
        mock_role_name = MagicMock()
        
        iam_resources._attach_managed_policies(
            pulumi_resource_name_prefix="test",
            role_name_for_log="TestRole",
            managed_policy_arns=[],
            iam_role_name=mock_role_name,
            opts=None
        )
        
        # Should not create any attachments
        mock_attachment_class.assert_not_called()


@patch('oidc_role_manager.iam_resources.aws.iam.RolePolicy')
class TestAttachInlinePolicies:
    """Test cases for _attach_inline_policies function."""
    
    def test_attach_inline_policies_success(self, mock_policy_class):
        """Test successful inline policy attachment."""
        mock_role_name = MagicMock()
        inline_policies = {
            "inline-CloudWatchLogs.json": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "logs:*"}]
            },
            "inline-S3Access.json": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:GetObject"}]
            }
        }
        
        iam_resources._attach_inline_policies(
            pulumi_resource_name_prefix="test",
            role_name_for_log="TestRole",
            inline_policies_map=inline_policies,
            iam_role_name=mock_role_name,
            opts=None
        )
        
        # Should create two inline policies
        assert mock_policy_class.call_count == 2
        
        calls = mock_policy_class.call_args_list
        
        # Check first policy
        assert calls[0][0] == ("test-inline-CloudWatchLogs",)
        assert calls[0][1]["role"] == mock_role_name
        assert calls[0][1]["name"] == "TestRole-CloudWatchLogs"
        
        # Check second policy
        assert calls[1][0] == ("test-inline-S3Access",)
        assert calls[1][1]["role"] == mock_role_name
        assert calls[1][1]["name"] == "TestRole-S3Access"
    
    def test_attach_inline_policies_empty_dict(self, mock_policy_class):
        """Test with empty inline policies dict."""
        mock_role_name = MagicMock()
        
        iam_resources._attach_inline_policies(
            pulumi_resource_name_prefix="test",
            role_name_for_log="TestRole",
            inline_policies_map={},
            iam_role_name=mock_role_name,
            opts=None
        )
        
        # Should not create any policies
        mock_policy_class.assert_not_called()


@patch('oidc_role_manager.iam_resources.pulumi.export')
class TestSafeExport:
    """Test cases for _safe_export function."""
    
    def test_safe_export_success(self, mock_export):
        """Test successful export."""
        mock_value = MagicMock()
        
        iam_resources._safe_export("test_key", mock_value)
        
        mock_export.assert_called_once_with("test_key", mock_value)
    
    def test_safe_export_exception_handled(self, mock_export):
        """Test that export exceptions are handled gracefully."""
        mock_export.side_effect = Exception("Not in Pulumi context")
        mock_value = MagicMock()
        
        # Should not raise exception
        iam_resources._safe_export("test_key", mock_value)
        
        mock_export.assert_called_once_with("test_key", mock_value)


class TestCreateIamRoleForGithubOidc:
    """Test cases for create_iam_role_for_github_oidc function."""
    
    @patch('oidc_role_manager.iam_resources._safe_export')
    @patch('oidc_role_manager.iam_resources._attach_inline_policies')
    @patch('oidc_role_manager.iam_resources._attach_managed_policies')
    @patch('oidc_role_manager.iam_resources._create_iam_role')
    @patch('oidc_role_manager.iam_resources._prepare_tags')
    @patch('oidc_role_manager.iam_resources._generate_github_assume_role_policy')
    @patch('oidc_role_manager.iam_resources._construct_github_oidc_provider_details')
    def test_create_iam_role_for_github_oidc_success(
        self, 
        mock_construct_oidc,
        mock_generate_policy,
        mock_prepare_tags,
        mock_create_role,
        mock_attach_managed,
        mock_attach_inline,
        mock_safe_export
    ):
        """Test successful IAM role creation for GitHub OIDC."""
        # Setup mocks
        mock_construct_oidc.return_value = (
            "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com",
            "token.actions.githubusercontent.com"
        )
        mock_generate_policy.return_value = '{"Version": "2012-10-17"}'
        mock_prepare_tags.return_value = {"Environment": "test"}
        
        mock_role = MagicMock()
        mock_role.name = "TestRole"
        mock_role.arn = "arn:aws:iam::123456789012:role/TestRole"
        mock_create_role.return_value = mock_role
        
        # Create test config
        config = RoleConfig(
            account_id="123456789012",
            role_name_dir="TestRole",
            details={
                "roleName": "TestRole",
                "oidcProviderUrl": "token.actions.githubusercontent.com",
                "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main",
                "audience": "sts.amazonaws.com",
                "description": "Test role"
            },
            managed_policies=["arn:aws:iam::aws:policy/ReadOnlyAccess"],
            inline_policies={"inline-test.json": {"Version": "2012-10-17"}},
            base_dir="/base"
        )
        
        # Execute
        result = iam_resources.create_iam_role_for_github_oidc(config)
        
        # Verify all functions were called correctly
        mock_construct_oidc.assert_called_once_with(
            "123456789012", 
            "token.actions.githubusercontent.com"
        )
        
        mock_generate_policy.assert_called_once_with(
            "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com",
            "token.actions.githubusercontent.com",
            "repo:org/repo:ref:refs/heads/main",
            "sts.amazonaws.com"
        )
        
        mock_prepare_tags.assert_called_once_with(config)
        
        mock_create_role.assert_called_once_with(
            pulumi_resource_name="123456789012-TestRole-role",
            role_name="TestRole",
            description="Test role",
            assume_role_policy_doc='{"Version": "2012-10-17"}',
            tags={"Environment": "test"},
            opts=None
        )
        
        mock_attach_managed.assert_called_once_with(
            pulumi_resource_name_prefix="123456789012-TestRole",
            role_name_for_log="TestRole",
            managed_policy_arns=["arn:aws:iam::aws:policy/ReadOnlyAccess"],
            iam_role_name="TestRole",
            opts=None
        )
        
        mock_attach_inline.assert_called_once_with(
            pulumi_resource_name_prefix="123456789012-TestRole",
            role_name_for_log="TestRole",
            inline_policies_map={"inline-test.json": {"Version": "2012-10-17"}},
            iam_role_name="TestRole",
            opts=None
        )
        
        # Should export role ARN and name
        expected_export_calls = [
            call("123456789012-TestRole_role_arn", mock_role.arn),
            call("123456789012-TestRole_role_name", mock_role.name)
        ]
        mock_safe_export.assert_has_calls(expected_export_calls)
        
        assert result == mock_role
    
    @patch('oidc_role_manager.iam_resources._construct_github_oidc_provider_details')
    def test_create_iam_role_for_github_oidc_with_provider(self, mock_construct_oidc):
        """Test IAM role creation with custom AWS provider."""
        mock_construct_oidc.return_value = (
            "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com",
            "token.actions.githubusercontent.com"
        )
        
        config = RoleConfig(
            account_id="123456789012",
            role_name_dir="TestRole",
            details={
                "roleName": "TestRole",
                "oidcProviderUrl": "token.actions.githubusercontent.com",
                "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
            },
            managed_policies=[],
            inline_policies={},
            base_dir="/base"
        )
        
        mock_provider = MagicMock()
        
        with patch('oidc_role_manager.iam_resources._create_iam_role') as mock_create_role:
            mock_role = MagicMock()
            mock_create_role.return_value = mock_role
            
            result = iam_resources.create_iam_role_for_github_oidc(config, mock_provider)
            
            # Should pass provider to create_role via opts
            call_args = mock_create_role.call_args
            opts = call_args[1]['opts']
            assert opts.provider == mock_provider
    
    def test_create_iam_role_for_github_oidc_default_audience(self):
        """Test IAM role creation with default audience."""
        config = RoleConfig(
            account_id="123456789012",
            role_name_dir="TestRole",
            details={
                "roleName": "TestRole",
                "oidcProviderUrl": "token.actions.githubusercontent.com",
                "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
                # No audience specified - should use default
            },
            managed_policies=[],
            inline_policies={},
            base_dir="/base"
        )
        
        with patch('oidc_role_manager.iam_resources._generate_github_assume_role_policy') as mock_generate_policy:
            with patch('oidc_role_manager.iam_resources._construct_github_oidc_provider_details') as mock_construct:
                mock_construct.return_value = ("arn", "url")
                mock_generate_policy.return_value = "{}"
                
                with patch('oidc_role_manager.iam_resources._create_iam_role') as mock_create_role:
                    mock_role = MagicMock()
                    mock_create_role.return_value = mock_role
                    
                    iam_resources.create_iam_role_for_github_oidc(config)
                    
                    # Should call with default audience
                    mock_generate_policy.assert_called_once_with(
                        "arn",
                        "url", 
                        "repo:org/repo:ref:refs/heads/main",
                        "sts.amazonaws.com"  # Default audience
                    ) 