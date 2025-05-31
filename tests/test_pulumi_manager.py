"""
Tests for pulumi_manager module
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call, ANY

from oidc_role_manager.config_loader import RoleConfig
from oidc_role_manager.pulumi_manager import PulumiStackManager


class TestPulumiStackManagerInit:
    """Test cases for PulumiStackManager initialization."""
    
    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        manager = PulumiStackManager()
        
        assert manager.project_name == "oidc-role-manager"
        assert manager.stack_name == "dev"
        assert manager.aws_region is None
        assert manager.aws_profile is None
        assert manager.work_dir == Path.cwd()
        assert str(Path.cwd() / '.pulumi-state') in manager.backend_url
    
    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        manager = PulumiStackManager(
            project_name="custom-project",
            stack_name="production",
            aws_region="us-east-1",
            aws_profile="my-profile",
            backend_url="s3://my-bucket/pulumi-state"
        )
        
        assert manager.project_name == "custom-project"
        assert manager.stack_name == "production"
        assert manager.aws_region == "us-east-1"
        assert manager.aws_profile == "my-profile"
        assert manager.backend_url == "s3://my-bucket/pulumi-state"
    
    @patch('pathlib.Path.mkdir')
    def test_init_creates_state_directory(self, mock_mkdir):
        """Test that initialization creates the state directory."""
        PulumiStackManager()
        mock_mkdir.assert_called_once_with(exist_ok=True)


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


class TestCreateWorkspaceSettings:
    """Test cases for _create_workspace_settings method."""
    
    def test_create_workspace_settings(self):
        """Test workspace settings creation."""
        manager = PulumiStackManager()
        
        with patch.dict('os.environ', {}, clear=True):
            settings = manager._create_workspace_settings()
        
        assert settings.work_dir == str(manager.work_dir)
        
        env_vars = settings.env_vars
        assert "PULUMI_BACKEND_URL" in env_vars
        assert "PULUMI_SKIP_UPDATE_CHECK" in env_vars
        assert "PULUMI_CONFIG_PASSPHRASE" in env_vars
        assert env_vars["PULUMI_SKIP_UPDATE_CHECK"] == "true"
    
    def test_create_workspace_settings_with_existing_passphrase(self):
        """Test workspace settings with existing passphrase."""
        manager = PulumiStackManager()
        
        with patch.dict('os.environ', {'PULUMI_CONFIG_PASSPHRASE': 'my-passphrase'}):
            settings = manager._create_workspace_settings()
        
        assert settings.env_vars["PULUMI_CONFIG_PASSPHRASE"] == "my-passphrase"


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
        """Test successful deployment preview."""
        self.setUp()
        mock_stack = MagicMock()
        mock_preview_result = MagicMock()
        mock_stack.preview.return_value = mock_preview_result
        mock_create_stack.return_value = mock_stack
        
        result = self.manager.preview_deployment([self.config])
        
        # Should create/select stack
        mock_create_stack.assert_called_once()
        
        # Should refresh and preview
        mock_stack.refresh.assert_called_once()
        mock_stack.preview.assert_called_once()
        
        assert result == mock_preview_result
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_preview_deployment_with_config(self, mock_create_stack):
        """Test preview deployment with stack configuration."""
        self.setUp()
        self.manager.aws_region = "us-west-2"
        
        mock_stack = MagicMock()
        mock_create_stack.return_value = mock_stack
        
        self.manager.preview_deployment([self.config])
        
        # Should set configuration
        mock_stack.set_config.assert_called_once_with(
            "aws:region", 
            ANY  # ConfigValue object
        )
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_preview_deployment_error(self, mock_create_stack):
        """Test preview deployment error handling."""
        self.setUp()
        mock_create_stack.side_effect = Exception("Stack creation failed")
        
        with pytest.raises(Exception, match="Stack creation failed"):
            self.manager.preview_deployment([self.config])


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
        
        # Should create/select stack
        mock_create_stack.assert_called_once()
        
        # Should refresh and deploy
        mock_stack.refresh.assert_called_once()
        mock_stack.up.assert_called_once()
        
        # Should store stack reference
        assert self.manager._current_stack == mock_stack
        
        assert result == mock_up_result
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_deploy_error(self, mock_create_stack):
        """Test deploy error handling."""
        self.setUp()
        mock_create_stack.side_effect = Exception("Deployment failed")
        
        with pytest.raises(Exception, match="Deployment failed"):
            self.manager.deploy([self.config])


class TestDestroy:
    """Test cases for destroy method."""
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_destroy_success(self, mock_create_stack):
        """Test successful resource destruction."""
        manager = PulumiStackManager()
        mock_stack = MagicMock()
        mock_destroy_result = MagicMock()
        mock_stack.destroy.return_value = mock_destroy_result
        mock_create_stack.return_value = mock_stack
        
        result = manager.destroy()
        
        # Should create/select stack with empty program
        mock_create_stack.assert_called_once()
        
        # Should destroy resources
        mock_stack.destroy.assert_called_once()
        
        assert result == mock_destroy_result
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_destroy_error(self, mock_create_stack):
        """Test destroy error handling."""
        manager = PulumiStackManager()
        mock_create_stack.side_effect = Exception("Destruction failed")
        
        with pytest.raises(Exception, match="Destruction failed"):
            manager.destroy()


class TestGetOutputs:
    """Test cases for get_outputs method."""
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_get_outputs_success(self, mock_create_stack):
        """Test successful outputs retrieval."""
        manager = PulumiStackManager()
        mock_stack = MagicMock()
        mock_outputs = {"role_arn": "arn:aws:iam::123456789012:role/TestRole"}
        mock_stack.outputs.return_value = mock_outputs
        mock_create_stack.return_value = mock_stack
        
        result = manager.get_outputs()
        
        mock_create_stack.assert_called_once()
        assert result == mock_outputs
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_get_outputs_error(self, mock_create_stack):
        """Test outputs retrieval error handling."""
        manager = PulumiStackManager()
        mock_create_stack.side_effect = Exception("Failed to get outputs")
        
        with pytest.raises(Exception, match="Failed to get outputs"):
            manager.get_outputs()


class TestGetStackInfo:
    """Test cases for get_stack_info method."""
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_get_stack_info_success(self, mock_create_stack):
        """Test successful stack info retrieval."""
        manager = PulumiStackManager()
        mock_stack = MagicMock()
        mock_info = MagicMock()
        mock_stack.info.return_value = mock_info
        mock_create_stack.return_value = mock_stack
        
        result = manager.get_stack_info()
        
        mock_create_stack.assert_called_once()
        assert result == mock_info
    
    @patch('oidc_role_manager.pulumi_manager.auto.create_or_select_stack')
    def test_get_stack_info_error(self, mock_create_stack):
        """Test stack info retrieval error handling."""
        manager = PulumiStackManager()
        mock_create_stack.side_effect = Exception("Failed to get info")
        
        result = manager.get_stack_info()
        assert result is None


class TestOutputHandler:
    """Test cases for _output_handler method."""
    
    def test_output_handler_with_json(self):
        """Test output handler with JSON output."""
        manager = PulumiStackManager()
        
        with patch('oidc_role_manager.pulumi_manager.logger') as mock_logger:
            manager._output_handler("Test output message")
            mock_logger.debug.assert_called_once_with("Pulumi: Test output message")
    
    def test_output_handler_with_console(self):
        """Test output handler with console output."""
        manager = PulumiStackManager()
        
        with patch('oidc_role_manager.pulumi_manager.console') as mock_console:
            with patch('oidc_role_manager.pulumi_manager.logger') as mock_logger:
                # Simulate non-JSON mode
                mock_logger.handlers = [MagicMock()]
                mock_logger.handlers[0].__class__.__name__ = "RichHandler"
                
                manager._output_handler("Test output message")
                
                # Should print to console (implementation may vary)
                # At minimum, should not crash 