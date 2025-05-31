"""
Tests for pulumi_manager module
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call, ANY

from oidc_role_manager.config_loader import RoleConfig
from oidc_role_manager.pulumi_manager import PulumiStackManager


@pytest.mark.unit
class TestPulumiStackManagerInit:
    """Test cases for PulumiStackManager initialization."""
    
    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        manager = PulumiStackManager()
        
        assert manager.project_name == "oidc-role-manager"
        assert manager.stack_name == "dev"
        assert manager.aws_region is None
        assert manager.aws_profile is None
        assert manager.assume_role_arn is None
        assert manager.external_id is None
        assert manager.work_dir == Path.cwd()
        assert str(Path.cwd() / '.pulumi-state') in manager.backend_url
    
    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        manager = PulumiStackManager(
            project_name="custom-project",
            stack_name="production",
            aws_region="us-east-1",
            aws_profile="my-profile",
            backend_url="s3://my-bucket/pulumi-state",
            assume_role_arn="arn:aws:iam::123456789012:role/CrossAccountRole",
            external_id="unique-external-id"
        )
        
        assert manager.project_name == "custom-project"
        assert manager.stack_name == "production"
        assert manager.aws_region == "us-east-1"
        assert manager.aws_profile == "my-profile"
        assert manager.backend_url == "s3://my-bucket/pulumi-state"
        assert manager.assume_role_arn == "arn:aws:iam::123456789012:role/CrossAccountRole"
        assert manager.external_id == "unique-external-id"
    
    @pytest.mark.backend
    @patch.dict(os.environ, {'PULUMI_BACKEND_URL': 's3://env-bucket/state'})
    def test_init_with_environment_backend_url(self):
        """Test initialization with backend URL from environment variable."""
        manager = PulumiStackManager()
        assert manager.backend_url == "s3://env-bucket/state"
    
    @pytest.mark.backend  
    def test_init_explicit_backend_url_overrides_env(self):
        """Test that explicit backend URL parameter overrides environment variable."""
        with patch.dict(os.environ, {'PULUMI_BACKEND_URL': 's3://env-bucket/state'}):
            manager = PulumiStackManager(backend_url="s3://explicit-bucket/state")
            assert manager.backend_url == "s3://explicit-bucket/state"
    
    @patch('pathlib.Path.mkdir')
    def test_init_creates_state_directory_for_local_backend(self, mock_mkdir):
        """Test that initialization creates the state directory for local backend."""
        PulumiStackManager()
        mock_mkdir.assert_called_once_with(exist_ok=True)
    
    @pytest.mark.backend
    @patch('pathlib.Path.mkdir')
    def test_init_does_not_create_directory_for_remote_backend(self, mock_mkdir):
        """Test that initialization doesn't create directory for remote backends."""
        PulumiStackManager(backend_url="s3://my-bucket/state")
        mock_mkdir.assert_not_called()


@pytest.mark.unit
class TestCreatePulumiProgram:
    """Test cases for _create_pulumi_program method."""
    
    def setUp(self):
        self.manager = PulumiStackManager()
        self.config = RoleConfig(
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
    
    @patch('oidc_role_manager.pulumi_manager.iam_resources.create_iam_role_for_github_oidc')
    @patch('oidc_role_manager.pulumi_manager.pulumi.export')
    def test_create_pulumi_program_without_aws_provider(self, mock_export, mock_create_role):
        """Test Pulumi program creation without AWS provider."""
        self.setUp()
        mock_role = MagicMock()
        mock_role.arn = "arn:aws:iam::123456789012:role/TestRole"
        mock_role.name = "TestRole"
        mock_create_role.return_value = mock_role
        
        program = self.manager._create_pulumi_program([self.config])
        result = program()
        
        # Should create role without provider
        mock_create_role.assert_called_once_with(self.config, None)
        
        # Should export role information
        mock_export.assert_has_calls([
            call("TestRole_arn", mock_role.arn),
            call("TestRole_name", mock_role.name)
        ], any_order=True)
        
        assert result == {"TestRole": mock_role}
    
    @patch('oidc_role_manager.pulumi_manager.iam_resources.create_iam_role_for_github_oidc')
    @patch('oidc_role_manager.pulumi_manager.pulumi.export')
    def test_create_pulumi_program_with_aws_provider(self, mock_export, mock_create_role):
        """Test Pulumi program creation with AWS provider."""
        self.setUp()
        self.manager.aws_region = "us-west-2"
        self.manager.aws_profile = "my-profile"
        
        mock_role = MagicMock()
        mock_role.arn = "arn:aws:iam::123456789012:role/TestRole"
        mock_role.name = "TestRole"
        mock_create_role.return_value = mock_role
        
        with patch('pulumi_aws.Provider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            
            program = self.manager._create_pulumi_program([self.config])
            result = program()
            
            # Should create AWS provider
            mock_provider_class.assert_called_once_with(
                "aws-provider",
                region="us-west-2",
                profile="my-profile"
            )
            
            # Should create role with provider
            mock_create_role.assert_called_once_with(self.config, mock_provider)
    
    @pytest.mark.cross_account
    @patch('oidc_role_manager.pulumi_manager.iam_resources.create_iam_role_for_github_oidc')
    @patch('oidc_role_manager.pulumi_manager.pulumi.export')
    def test_create_pulumi_program_with_cross_account_role_assumption(self, mock_export, mock_create_role):
        """Test Pulumi program creation with cross-account role assumption."""
        self.setUp()
        self.manager.aws_region = "us-west-2"
        self.manager.aws_profile = "base-profile"
        self.manager.assume_role_arn = "arn:aws:iam::123456789012:role/CrossAccountRole"
        self.manager.external_id = "unique-external-id"
        
        mock_role = MagicMock()
        mock_role.arn = "arn:aws:iam::123456789012:role/TestRole"
        mock_role.name = "TestRole"
        mock_create_role.return_value = mock_role
        
        with patch('pulumi_aws.Provider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            
            program = self.manager._create_pulumi_program([self.config])
            result = program()
            
            # Should create AWS provider with cross-account role assumption
            expected_assume_role = {
                "role_arn": "arn:aws:iam::123456789012:role/CrossAccountRole",
                "session_name": f"oidc-role-manager-{self.manager.stack_name}",
                "external_id": "unique-external-id"
            }
            mock_provider_class.assert_called_once_with(
                "aws-provider",
                region="us-west-2",
                profile="base-profile",
                assume_role=expected_assume_role
            )
            
            # Should create role with provider
            mock_create_role.assert_called_once_with(self.config, mock_provider)
    
    @pytest.mark.cross_account
    @patch('oidc_role_manager.pulumi_manager.iam_resources.create_iam_role_for_github_oidc')
    @patch('oidc_role_manager.pulumi_manager.pulumi.export')
    def test_create_pulumi_program_with_role_assumption_no_external_id(self, mock_export, mock_create_role):
        """Test Pulumi program creation with role assumption but no external ID."""
        self.setUp()
        self.manager.aws_region = "us-west-2"
        self.manager.assume_role_arn = "arn:aws:iam::123456789012:role/CrossAccountRole"
        # external_id is None
        
        mock_role = MagicMock()
        mock_create_role.return_value = mock_role
        
        with patch('pulumi_aws.Provider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            
            program = self.manager._create_pulumi_program([self.config])
            result = program()
            
            # Should create AWS provider with role assumption but no external_id
            expected_assume_role = {
                "role_arn": "arn:aws:iam::123456789012:role/CrossAccountRole",
                "session_name": f"oidc-role-manager-{self.manager.stack_name}"
            }
            mock_provider_class.assert_called_once_with(
                "aws-provider",
                region="us-west-2",
                assume_role=expected_assume_role
            )
    
    @patch('oidc_role_manager.pulumi_manager.iam_resources.create_iam_role_for_github_oidc')
    def test_create_pulumi_program_with_multiple_roles(self, mock_create_role):
        """Test Pulumi program creation with multiple roles."""
        self.setUp()
        config2 = RoleConfig(
            account_id="123456789012",
            role_name_dir="TestRole2",
            details={
                "roleName": "GitHubActionTestRole2",
                "oidcProviderUrl": "token.actions.githubusercontent.com",
                "githubSubjectClaim": "repo:org/repo:environment:prod"
            },
            managed_policies=[],
            inline_policies={},
            base_dir="/base"
        )
        
        mock_role1 = MagicMock()
        mock_role1.arn = "arn1"
        mock_role1.name = "GitHubActionTestRole"
        
        mock_role2 = MagicMock()
        mock_role2.arn = "arn2"
        mock_role2.name = "GitHubActionTestRole2"
        
        mock_create_role.side_effect = [mock_role1, mock_role2]
        
        with patch('oidc_role_manager.pulumi_manager.pulumi.export'):
            program = self.manager._create_pulumi_program([self.config, config2])
            result = program()
            
            # Should create both roles
            assert mock_create_role.call_count == 2
            assert len(result) == 2
    
    @patch('oidc_role_manager.pulumi_manager.iam_resources.create_iam_role_for_github_oidc')
    def test_create_pulumi_program_role_creation_error(self, mock_create_role):
        """Test Pulumi program handles role creation errors."""
        self.setUp()
        mock_create_role.side_effect = Exception("Role creation failed")
        
        program = self.manager._create_pulumi_program([self.config])
        
        with pytest.raises(Exception, match="Role creation failed"):
            program()


@pytest.mark.unit
class TestGetStackConfig:
    """Test cases for _get_stack_config method."""
    
    def test_get_stack_config_empty(self):
        """Test stack config with no AWS settings."""
        manager = PulumiStackManager()
        config = manager._get_stack_config()
        assert config == {}
    
    def test_get_stack_config_with_region(self):
        """Test stack config with AWS region."""
        manager = PulumiStackManager(aws_region="us-east-1")
        config = manager._get_stack_config()
        assert config == {"aws:region": "us-east-1"}
    
    def test_get_stack_config_with_profile(self):
        """Test stack config with AWS profile."""
        manager = PulumiStackManager(aws_profile="my-profile")
        config = manager._get_stack_config()
        assert config == {"aws:profile": "my-profile"}
    
    def test_get_stack_config_with_both(self):
        """Test stack config with both region and profile."""
        manager = PulumiStackManager(aws_region="us-west-2", aws_profile="my-profile")
        config = manager._get_stack_config()
        expected = {
            "aws:region": "us-west-2",
            "aws:profile": "my-profile"
        }
        assert config == expected


@pytest.mark.unit
@pytest.mark.backend
class TestCreateWorkspaceSettings:
    """Test cases for _create_workspace_settings method."""
    
    def test_create_workspace_settings(self):
        """Test workspace settings creation with local backend."""
        manager = PulumiStackManager()
        settings = manager._create_workspace_settings()
        
        assert settings.work_dir == str(Path.cwd())
        assert "PULUMI_BACKEND_URL" in settings.env_vars
        assert settings.env_vars["PULUMI_BACKEND_URL"] == manager.backend_url
        assert settings.env_vars["PULUMI_SKIP_UPDATE_CHECK"] == "true"
        assert "PULUMI_CONFIG_PASSPHRASE" in settings.env_vars
    
    def test_create_workspace_settings_with_s3_backend(self):
        """Test workspace settings creation with S3 backend."""
        manager = PulumiStackManager(backend_url="s3://my-bucket/state")
        settings = manager._create_workspace_settings()
        
        assert settings.env_vars["PULUMI_BACKEND_URL"] == "s3://my-bucket/state"
    
    @patch.dict(os.environ, {'PULUMI_CONFIG_PASSPHRASE': 'existing-passphrase'})
    def test_create_workspace_settings_with_existing_passphrase(self):
        """Test workspace settings uses existing passphrase from environment."""
        manager = PulumiStackManager()
        settings = manager._create_workspace_settings()
        
        assert settings.env_vars["PULUMI_CONFIG_PASSPHRASE"] == "existing-passphrase"


@pytest.mark.integration
class TestPreviewDeployment:
    """Test cases for preview_deployment method."""
    
    def setUp(self):
        self.manager = PulumiStackManager()
        self.config = RoleConfig(
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
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_preview_deployment_success(self, mock_create_stack):
        """Test successful preview deployment."""
        self.setUp()
        mock_stack = MagicMock()
        mock_preview_result = MagicMock()
        mock_stack.preview.return_value = mock_preview_result
        mock_create_stack.return_value = mock_stack
        
        result = self.manager.preview_deployment([self.config])
        
        # Verify stack operations
        mock_create_stack.assert_called_once()
        mock_stack.refresh.assert_called_once()
        mock_stack.preview.assert_called_once()
        assert result == mock_preview_result
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_preview_deployment_with_config(self, mock_create_stack):
        """Test preview deployment with AWS configuration."""
        self.setUp()
        self.manager.aws_region = "us-west-2"
        self.manager.aws_profile = "my-profile"
        
        mock_stack = MagicMock()
        mock_create_stack.return_value = mock_stack
        
        self.manager.preview_deployment([self.config])
        
        # Should set configuration
        expected_calls = [
            call("aws:region", ANY),
            call("aws:profile", ANY)
        ]
        mock_stack.set_config.assert_has_calls(expected_calls, any_order=True)
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_preview_deployment_error(self, mock_create_stack):
        """Test preview deployment with error."""
        self.setUp()
        mock_create_stack.side_effect = Exception("Preview failed")
        
        with pytest.raises(Exception, match="Preview failed"):
            self.manager.preview_deployment([self.config])


@pytest.mark.integration
class TestDeploy:
    """Test cases for deploy method."""
    
    def setUp(self):
        self.manager = PulumiStackManager()
        self.config = RoleConfig(
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
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_deploy_success(self, mock_create_stack):
        """Test successful deployment."""
        self.setUp()
        mock_stack = MagicMock()
        mock_up_result = MagicMock()
        mock_stack.up.return_value = mock_up_result
        mock_create_stack.return_value = mock_stack
        
        result = self.manager.deploy([self.config])
        
        # Verify stack operations
        mock_create_stack.assert_called_once()
        mock_stack.refresh.assert_called_once()
        mock_stack.up.assert_called_once()
        assert result == mock_up_result
        # Should store current stack
        assert hasattr(self.manager, '_current_stack')
        assert self.manager._current_stack == mock_stack
    
    @pytest.mark.cross_account
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_deploy_with_cross_account_authentication(self, mock_create_stack):
        """Test deployment with cross-account authentication."""
        self.setUp()
        self.manager.assume_role_arn = "arn:aws:iam::123456789012:role/CrossAccountRole"
        self.manager.external_id = "unique-external-id"
        
        mock_stack = MagicMock()
        mock_create_stack.return_value = mock_stack
        
        self.manager.deploy([self.config])
        
        # Should create stack with cross-account config
        mock_create_stack.assert_called_once()
        call_args = mock_create_stack.call_args
        assert call_args[1]['stack_name'] == self.manager.stack_name
        assert call_args[1]['project_name'] == self.manager.project_name
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_deploy_error(self, mock_create_stack):
        """Test deployment with error."""
        self.setUp()
        mock_create_stack.side_effect = Exception("Deploy failed")
        
        with pytest.raises(Exception, match="Deploy failed"):
            self.manager.deploy([self.config])


@pytest.mark.integration
class TestDestroy:
    """Test cases for destroy method."""
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_destroy_success(self, mock_create_stack):
        """Test successful destroy operation."""
        manager = PulumiStackManager()
        mock_stack = MagicMock()
        mock_destroy_result = MagicMock()
        mock_stack.destroy.return_value = mock_destroy_result
        mock_create_stack.return_value = mock_stack
        
        result = manager.destroy()
        
        # Verify stack operations
        mock_create_stack.assert_called_once()
        mock_stack.destroy.assert_called_once()
        assert result == mock_destroy_result
    
    @pytest.mark.backend
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_destroy_with_backend_url(self, mock_create_stack):
        """Test destroy operation with custom backend URL."""
        manager = PulumiStackManager(backend_url="s3://my-bucket/state")
        mock_stack = MagicMock()
        mock_create_stack.return_value = mock_stack
        
        manager.destroy()
        
        # Should use custom backend URL in workspace settings
        call_args = mock_create_stack.call_args
        workspace_opts = call_args[1]['opts']
        assert workspace_opts.env_vars["PULUMI_BACKEND_URL"] == "s3://my-bucket/state"
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_destroy_error(self, mock_create_stack):
        """Test destroy operation with error."""
        manager = PulumiStackManager()
        mock_create_stack.side_effect = Exception("Destroy failed")
        
        with pytest.raises(Exception, match="Destroy failed"):
            manager.destroy()


@pytest.mark.unit
class TestGetOutputs:
    """Test cases for get_outputs method."""
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_get_outputs_success(self, mock_create_stack):
        """Test successful get outputs operation."""
        manager = PulumiStackManager()
        mock_stack = MagicMock()
        mock_outputs = {"role_arn": "arn:aws:iam::123456789012:role/TestRole"}
        mock_stack.outputs.return_value = mock_outputs
        mock_create_stack.return_value = mock_stack
        
        result = manager.get_outputs()
        
        mock_create_stack.assert_called_once()
        mock_stack.outputs.assert_called_once()
        assert result == mock_outputs
    
    def test_get_outputs_from_current_stack(self):
        """Test get outputs using stored current stack."""
        manager = PulumiStackManager()
        mock_stack = MagicMock()
        mock_outputs = {"role_arn": "arn:aws:iam::123456789012:role/TestRole"}
        mock_stack.outputs.return_value = mock_outputs
        
        # Set current stack
        manager._current_stack = mock_stack
        
        result = manager.get_outputs()
        
        # Should use current stack, not create new one
        mock_stack.outputs.assert_called_once()
        assert result == mock_outputs
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_get_outputs_error(self, mock_create_stack):
        """Test get outputs with error."""
        manager = PulumiStackManager()
        mock_create_stack.side_effect = Exception("Get outputs failed")
        
        with pytest.raises(Exception, match="Get outputs failed"):
            manager.get_outputs()


@pytest.mark.unit
class TestGetStackInfo:
    """Test cases for get_stack_info method."""
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_get_stack_info_success(self, mock_create_stack):
        """Test successful get stack info operation."""
        manager = PulumiStackManager()
        mock_stack = MagicMock()
        mock_info = MagicMock()
        mock_stack.info.return_value = mock_info
        mock_create_stack.return_value = mock_stack
        
        result = manager.get_stack_info()
        
        mock_create_stack.assert_called_once()
        mock_stack.info.assert_called_once()
        assert result == mock_info
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_get_stack_info_error(self, mock_create_stack):
        """Test get stack info with error returns None."""
        manager = PulumiStackManager()
        mock_create_stack.side_effect = Exception("Stack not found")
        
        result = manager.get_stack_info()
        
        # Should return None on error
        assert result is None


@pytest.mark.unit
class TestOutputHandler:
    """Test cases for _output_handler method."""
    
    def test_output_handler_filters_noisy_messages(self):
        """Test output handler filters out noisy messages."""
        manager = PulumiStackManager()
        
        # These should be filtered out
        noisy_messages = [
            "Downloading plugin...",
            "Installing provider...",
            "diagnostic: some warning"
        ]
        
        with patch('oidc_role_manager.pulumi_manager.logger') as mock_logger:
            for message in noisy_messages:
                manager._output_handler(message)
            
            # Should not log any of these
            mock_logger.error.assert_not_called()
            mock_logger.warning.assert_not_called()
            mock_logger.debug.assert_not_called()
    
    def test_output_handler_logs_errors_and_warnings(self):
        """Test output handler properly logs errors and warnings."""
        manager = PulumiStackManager()
        
        with patch('oidc_role_manager.pulumi_manager.logger') as mock_logger:
            # Test error logging
            manager._output_handler("error: Something went wrong")
            mock_logger.error.assert_called_with("Pulumi: error: Something went wrong")
            
            # Test warning logging
            manager._output_handler("warning: This is a warning")
            mock_logger.warning.assert_called_with("Pulumi: warning: This is a warning")
            
            # Test normal output logging
            manager._output_handler("Normal output message")
            mock_logger.debug.assert_called_with("Pulumi: Normal output message")


@pytest.mark.cross_account
@pytest.mark.security
class TestCrossAccountAuthentication:
    """Test cases specifically for cross-account authentication features."""
    
    def test_cross_account_session_name_generation(self):
        """Test that cross-account session names are properly generated."""
        manager = PulumiStackManager(
            stack_name="prod-123456789012",
            assume_role_arn="arn:aws:iam::123456789012:role/CrossAccountRole",
            aws_region="us-west-2"  # Need to specify region to trigger provider creation
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
        
        with patch('pulumi_aws.Provider') as mock_provider_class:
            # Set up the mock provider to be called with expected arguments
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            
            with patch('oidc_role_manager.pulumi_manager.iam_resources.create_iam_role_for_github_oidc') as mock_create_role:
                with patch('oidc_role_manager.pulumi_manager.pulumi.export') as mock_export:
                    # Mock the role creation to return a mock role
                    mock_role = MagicMock()
                    mock_role.arn = "arn:aws:iam::123456789012:role/TestRole"
                    mock_role.name = "TestRole"
                    mock_create_role.return_value = mock_role
                    
                    program = manager._create_pulumi_program([config])
                    program()
                    
                    # Check that Provider was called
                    mock_provider_class.assert_called_once()
                    call_args = mock_provider_class.call_args
                    
                    # Verify the assume_role configuration
                    assume_role_config = call_args[1]['assume_role']
                    assert assume_role_config['session_name'] == "oidc-role-manager-prod-123456789012"
                    
                    # Verify export was called
                    assert mock_export.call_count >= 2  # Should export arn and name
    
    def test_external_id_security_logging(self):
        """Test that external IDs are properly handled in logging."""
        manager = PulumiStackManager(
            assume_role_arn="arn:aws:iam::123456789012:role/CrossAccountRole",
            external_id="sensitive-external-id"
        )
        
        # External ID should be stored but never logged in plain text
        assert manager.external_id == "sensitive-external-id"
        
        # In real logging scenarios, external ID should be masked
        # This is tested in the CLI tests where deployment_info masks it


@pytest.mark.backend
class TestBackendConfiguration:
    """Test cases for different backend configurations."""
    
    def test_s3_backend_configuration(self):
        """Test S3 backend configuration."""
        manager = PulumiStackManager(backend_url="s3://my-bucket/pulumi-state/oidc-roles")
        settings = manager._create_workspace_settings()
        
        assert settings.env_vars["PULUMI_BACKEND_URL"] == "s3://my-bucket/pulumi-state/oidc-roles"
    
    def test_azure_blob_backend_configuration(self):
        """Test Azure Blob Storage backend configuration."""
        manager = PulumiStackManager(backend_url="azblob://my-container/pulumi-state")
        settings = manager._create_workspace_settings()
        
        assert settings.env_vars["PULUMI_BACKEND_URL"] == "azblob://my-container/pulumi-state"
    
    def test_pulumi_cloud_backend_configuration(self):
        """Test Pulumi Cloud backend configuration."""
        manager = PulumiStackManager(backend_url="")
        settings = manager._create_workspace_settings()
        
        assert settings.env_vars["PULUMI_BACKEND_URL"] == ""
    
    @patch.dict(os.environ, {'PULUMI_BACKEND_URL': 'gs://my-gcs-bucket/state'})
    def test_gcs_backend_from_environment(self):
        """Test Google Cloud Storage backend from environment variable."""
        manager = PulumiStackManager()
        assert manager.backend_url == "gs://my-gcs-bucket/state" 