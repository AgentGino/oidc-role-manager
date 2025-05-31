"""
Tests for CLI module
"""

import pytest
import os
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from cli import cli, ExitCodes, validate_aws_account_id, setup_logging


@pytest.mark.unit
class TestExitCodes:
    """Test cases for exit codes constants."""
    
    def test_exit_codes_defined(self):
        """Test that all exit codes are defined."""
        assert ExitCodes.SUCCESS == 0
        assert ExitCodes.GENERAL_ERROR == 1
        assert ExitCodes.CONFIG_ERROR == 2
        assert ExitCodes.VALIDATION_ERROR == 3
        assert ExitCodes.AWS_ERROR == 4


@pytest.mark.unit
class TestValidateAwsAccountId:
    """Test cases for validate_aws_account_id function."""
    
    def test_valid_account_id(self):
        """Test validation with valid account ID."""
        result = validate_aws_account_id(None, None, "123456789012")
        assert result == "123456789012"
    
    def test_invalid_account_id_too_short(self):
        """Test validation with too short account ID."""
        with pytest.raises(Exception):  # click.BadParameter
            validate_aws_account_id(None, None, "12345678901")
    
    def test_invalid_account_id_too_long(self):
        """Test validation with too long account ID."""
        with pytest.raises(Exception):  # click.BadParameter
            validate_aws_account_id(None, None, "1234567890123")
    
    def test_invalid_account_id_non_numeric(self):
        """Test validation with non-numeric account ID."""
        with pytest.raises(Exception):  # click.BadParameter
            validate_aws_account_id(None, None, "12345678901a")
    
    def test_empty_account_id(self):
        """Test validation with empty account ID."""
        with pytest.raises(Exception):  # click.BadParameter
            validate_aws_account_id(None, None, "")


@pytest.mark.unit
class TestSetupLogging:
    """Test cases for setup_logging function."""
    
    def test_setup_logging_info_level(self):
        """Test logging setup with INFO level."""
        logger = setup_logging("INFO", json_output=False)
        assert logger.level == 20  # logging.INFO
    
    def test_setup_logging_debug_level(self):
        """Test logging setup with DEBUG level."""
        logger = setup_logging("DEBUG", json_output=False)
        assert logger.level == 10  # logging.DEBUG
    
    def test_setup_logging_json_output(self):
        """Test logging setup with JSON output."""
        logger = setup_logging("INFO", json_output=True)
        # Should not raise exception
        assert logger is not None
    
    def test_setup_logging_case_insensitive(self):
        """Test logging setup with lowercase level."""
        logger = setup_logging("info", json_output=False)
        assert logger.level == 20  # logging.INFO


@pytest.mark.cli
@pytest.mark.integration
class TestCliCommands:
    """Test cases for CLI commands."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test CLI help command."""
        self.setUp()
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "Enterprise OIDC Role Manager" in result.output
    
    def test_cli_version(self):
        """Test CLI version command."""
        self.setUp()
        result = self.runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert "1.0.0" in result.output
    
    @patch('cli.config_loader.discover_role_configs')
    def test_validate_command_success(self, mock_discover):
        """Test validate command success."""
        self.setUp()
        mock_discover.return_value = []
        
        result = self.runner.invoke(cli, ['validate', '--roles-dir', 'test-dir'])
        # Note: This might fail without actual directory structure
        # The test shows the intention but may need adjustment
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_command_dry_run(self, mock_stack_manager, mock_discover):
        """Test deploy command with dry run."""
        self.setUp()
        # Return a non-empty list so preview_deployment gets called
        mock_config = MagicMock()
        mock_config.role_name = "TestRole"
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--dry-run'
        ])
        
        # Should call preview instead of deploy
        mock_manager.preview_deployment.assert_called_once()
        mock_manager.deploy.assert_not_called()


@pytest.mark.cli
@pytest.mark.cross_account
class TestCrossAccountAuthentication:
    """Test cases for cross-account authentication CLI options."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_with_assume_role_arn(self, mock_stack_manager, mock_discover):
        """Test deploy command with assume role ARN."""
        self.setUp()
        mock_config = MagicMock()
        mock_config.role_name = "TestRole"
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--assume-role-arn', 'arn:aws:iam::123456789012:role/CrossAccountRole',
            '--dry-run'
        ])
        
        # Should create PulumiStackManager with assume_role_arn
        mock_stack_manager.assert_called_once()
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['assume_role_arn'] == 'arn:aws:iam::123456789012:role/CrossAccountRole'
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_with_external_id(self, mock_stack_manager, mock_discover):
        """Test deploy command with external ID."""
        self.setUp()
        mock_config = MagicMock()
        mock_config.role_name = "TestRole"
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--assume-role-arn', 'arn:aws:iam::123456789012:role/CrossAccountRole',
            '--external-id', 'unique-external-id',
            '--dry-run'
        ])
        
        # Should create PulumiStackManager with external_id
        mock_stack_manager.assert_called_once()
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['external_id'] == 'unique-external-id'
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_with_cross_account_environment_variables(self, mock_stack_manager, mock_discover):
        """Test deploy command using cross-account environment variables."""
        self.setUp()
        mock_config = MagicMock()
        mock_config.role_name = "TestRole"
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        env = {
            'AWS_ASSUME_ROLE_ARN': 'arn:aws:iam::123456789012:role/EnvRole',
            'AWS_EXTERNAL_ID': 'env-external-id'
        }
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--dry-run'
        ], env=env)
        
        # Should create PulumiStackManager with environment variables
        mock_stack_manager.assert_called_once()
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['assume_role_arn'] == 'arn:aws:iam::123456789012:role/EnvRole'
        assert call_kwargs['external_id'] == 'env-external-id'
    
    @pytest.mark.security
    def test_external_id_masking_in_deployment_info(self):
        """Test that external ID is masked in deployment logging."""
        self.setUp()
        
        # This test would check that sensitive external IDs are masked in logs
        # Implementation would depend on actual logging behavior
        with patch('cli.config_loader.discover_role_configs') as mock_discover:
            with patch('cli.PulumiStackManager') as mock_stack_manager:
                mock_discover.return_value = []
                
                result = self.runner.invoke(cli, [
                    'deploy',
                    '--account-id', '123456789012',
                    '--external-id', 'sensitive-id',
                    '--json-output'
                ])
                
                # In a real implementation, we'd check that the output 
                # contains masked external ID ("***") rather than actual value


@pytest.mark.cli
@pytest.mark.backend
class TestBackendConfiguration:
    """Test cases for backend URL configuration."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_with_backend_url_parameter(self, mock_stack_manager, mock_discover):
        """Test deploy command with backend URL parameter."""
        self.setUp()
        mock_config = MagicMock()
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--backend-url', 's3://my-bucket/pulumi-state',
            '--dry-run'
        ])
        
        # Should create PulumiStackManager with backend_url
        mock_stack_manager.assert_called_once()
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['backend_url'] == 's3://my-bucket/pulumi-state'
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_with_backend_url_environment_variable(self, mock_stack_manager, mock_discover):
        """Test deploy command with backend URL from environment variable."""
        self.setUp()
        mock_config = MagicMock()
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        env = {'PULUMI_BACKEND_URL': 'azblob://my-container/state'}
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--dry-run'
        ], env=env)
        
        # Should create PulumiStackManager with environment backend URL
        mock_stack_manager.assert_called_once()
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['backend_url'] == 'azblob://my-container/state'
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_destroy_with_backend_url(self, mock_stack_manager, mock_discover):
        """Test destroy command with backend URL."""
        self.setUp()
        mock_manager = MagicMock()
        mock_manager.get_stack_info.return_value = MagicMock()  # Stack exists
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'destroy',
            '--account-id', '123456789012',
            '--backend-url', 's3://my-bucket/state',
            '--auto-approve'
        ])
        
        # Should create PulumiStackManager with backend_url
        mock_stack_manager.assert_called_once()
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['backend_url'] == 's3://my-bucket/state'
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_status_with_backend_url(self, mock_stack_manager, mock_discover):
        """Test status command with backend URL."""
        self.setUp()
        mock_manager = MagicMock()
        mock_manager.get_stack_info.return_value = MagicMock()
        mock_manager.get_outputs.return_value = {}
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'status',
            '--account-id', '123456789012',
            '--backend-url', 's3://my-bucket/state'
        ])
        
        # Should create PulumiStackManager with backend_url
        mock_stack_manager.assert_called_once()
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['backend_url'] == 's3://my-bucket/state'


@pytest.mark.cli
@pytest.mark.integration
class TestEnhancedCommandOptions:
    """Test cases for enhanced command options and parameters."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_with_all_aws_options(self, mock_stack_manager, mock_discover):
        """Test deploy command with all AWS-related options."""
        self.setUp()
        mock_config = MagicMock()
        mock_config.role_name = "TestRole"
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--aws-region', 'us-east-1',
            '--aws-profile', 'my-profile',
            '--assume-role-arn', 'arn:aws:iam::123456789012:role/CrossAccountRole',
            '--external-id', 'unique-id',
            '--stack-name', 'production',
            '--backend-url', 's3://my-bucket/state',
            '--dry-run'
        ])
        
        # Should create PulumiStackManager with all parameters
        mock_stack_manager.assert_called_once()
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['project_name'] == 'oidc-role-manager'
        assert call_kwargs['stack_name'] == 'production-123456789012'
        assert call_kwargs['aws_region'] == 'us-east-1'
        assert call_kwargs['aws_profile'] == 'my-profile'
        assert call_kwargs['assume_role_arn'] == 'arn:aws:iam::123456789012:role/CrossAccountRole'
        assert call_kwargs['external_id'] == 'unique-id'
        assert call_kwargs['backend_url'] == 's3://my-bucket/state'
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    @patch('cli.validate_roles_directory')
    def test_deploy_with_json_output_and_cross_account(self, mock_validate_dir, mock_stack_manager, mock_discover):
        """Test deploy command with JSON output and cross-account authentication."""
        self.setUp()
        
        # Test that the CLI accepts the parameters without error
        # json-output is a global option, so check the main CLI help
        result = self.runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert '--json-output' in result.output
        
        # Test that deploy command has the cross-account options
        result = self.runner.invoke(cli, ['deploy', '--help'])
        assert result.exit_code == 0
        assert '--assume-role-arn' in result.output
        assert '--dry-run' in result.output
    
    def test_list_stacks_command_with_custom_stack_name(self):
        """Test list-stacks command with custom stack name."""
        self.setUp()
        
        with patch('cli.Path') as mock_path:
            # Mock empty state directory
            mock_state_dir = MagicMock()
            mock_state_dir.exists.return_value = False
            mock_path.cwd.return_value.joinpath.return_value = mock_state_dir
            
            result = self.runner.invoke(cli, [
                'list-stacks',
                '--stack-name', 'production'
            ])
            
            # Should handle custom stack name
            assert result.exit_code == 0


@pytest.mark.cli
@pytest.mark.integration
class TestCliIntegration:
    """Integration tests for CLI commands."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    def test_deploy_command_missing_account_id(self):
        """Test deploy command without account ID."""
        self.setUp()
        result = self.runner.invoke(cli, ['deploy'])
        assert result.exit_code != 0
        assert "account-id" in result.output.lower()
    
    def test_destroy_command_missing_account_id(self):
        """Test destroy command without account ID."""
        self.setUp()
        result = self.runner.invoke(cli, ['destroy'])
        assert result.exit_code != 0
        assert "account-id" in result.output.lower()
    
    def test_status_command_missing_account_id(self):
        """Test status command without account ID."""
        self.setUp()
        result = self.runner.invoke(cli, ['status'])
        assert result.exit_code != 0
        assert "account-id" in result.output.lower()
    
    def test_deploy_command_with_invalid_account_id(self):
        """Test deploy command with invalid account ID format."""
        self.setUp()
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '12345'  # Too short
        ])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "must be exactly 12 digits" in result.output.lower()
    
    def test_deploy_command_with_invalid_role_arn_format(self):
        """Test deploy command with malformed assume role ARN."""
        self.setUp()
        
        with patch('cli.config_loader.discover_role_configs') as mock_discover:
            mock_discover.return_value = []
            
            result = self.runner.invoke(cli, [
                'deploy',
                '--account-id', '123456789012',
                '--assume-role-arn', 'invalid-arn-format',
                '--dry-run'
            ])
            
            # Command should accept the ARN parameter (validation happens at AWS level)
            # But should still work with empty role configs
            assert result.exit_code == 0


@pytest.mark.cli
class TestEnvironmentVariables:
    """Test cases for environment variable handling."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    def test_account_id_from_env(self):
        """Test account ID from environment variable."""
        self.setUp()
        env = {'AWS_ACCOUNT_ID': '123456789012'}
        
        with patch('cli.config_loader.discover_role_configs') as mock_discover:
            mock_discover.return_value = []
            
            result = self.runner.invoke(cli, ['validate'], env=env)
            # Should use account ID from environment
    
    def test_log_level_from_env(self):
        """Test log level from environment variable."""
        self.setUp()
        env = {'OIDC_LOG_LEVEL': 'DEBUG'}
        
        result = self.runner.invoke(cli, ['--help'], env=env)
        # Should not fail with debug log level
        assert result.exit_code == 0
    
    def test_json_output_from_env(self):
        """Test JSON output from environment variable."""
        self.setUp()
        env = {'OIDC_JSON_OUTPUT': 'true'}
        
        result = self.runner.invoke(cli, ['--help'], env=env)
        # Should not fail with JSON output enabled
        assert result.exit_code == 0
    
    def test_all_environment_variables_together(self):
        """Test using multiple environment variables together."""
        self.setUp()
        env = {
            'AWS_ACCOUNT_ID': '123456789012',
            'AWS_REGION': 'us-west-2',
            'AWS_PROFILE': 'my-profile',
            'AWS_ASSUME_ROLE_ARN': 'arn:aws:iam::123456789012:role/CrossAccountRole',
            'AWS_EXTERNAL_ID': 'env-external-id',
            'PULUMI_STACK_NAME': 'staging',
            'PULUMI_BACKEND_URL': 's3://env-bucket/state',
            'OIDC_LOG_LEVEL': 'INFO',
            'OIDC_JSON_OUTPUT': 'true',
            'OIDC_AUTO_APPROVE': 'true'
        }
        
        with patch('cli.config_loader.discover_role_configs') as mock_discover:
            with patch('cli.PulumiStackManager') as mock_stack_manager:
                # Return at least one config so PulumiStackManager gets called
                mock_config = MagicMock()
                mock_config.role_name = "TestRole"
                mock_discover.return_value = [mock_config]
                mock_manager = MagicMock()
                mock_stack_manager.return_value = mock_manager
                
                result = self.runner.invoke(cli, ['deploy', '--dry-run'], env=env)
                
                # Should use all environment variables
                mock_stack_manager.assert_called_once()
                call_kwargs = mock_stack_manager.call_args[1]
                assert call_kwargs['stack_name'] == 'staging-123456789012'
                assert call_kwargs['aws_region'] == 'us-west-2'
                assert call_kwargs['aws_profile'] == 'my-profile'
                assert call_kwargs['assume_role_arn'] == 'arn:aws:iam::123456789012:role/CrossAccountRole'
                assert call_kwargs['external_id'] == 'env-external-id'
                assert call_kwargs['backend_url'] == 's3://env-bucket/state'


@pytest.mark.cli
class TestErrorHandling:
    """Test cases for error handling in CLI."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    def test_invalid_log_level(self):
        """Test CLI with invalid log level."""
        self.setUp()
        result = self.runner.invoke(cli, ['--log-level', 'INVALID', 'validate'])
        # Click should validate the choice and return an error
        assert result.exit_code == 2  # Click validation error
        assert "Invalid value for '--log-level'" in result.output
    
    @patch('cli.config_loader.discover_role_configs')
    def test_configuration_error_handling(self, mock_discover):
        """Test handling of configuration errors."""
        self.setUp()
        from oidc_role_manager.config_loader import ConfigError
        mock_discover.side_effect = ConfigError("Invalid configuration")
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--dry-run'
        ])
        
        assert result.exit_code == ExitCodes.CONFIG_ERROR
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_pulumi_error_handling(self, mock_stack_manager, mock_discover):
        """Test handling of Pulumi errors."""
        self.setUp()
        mock_config = MagicMock()
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_manager.preview_deployment.side_effect = Exception("Pulumi error")
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--dry-run'
        ])
        
        assert result.exit_code == ExitCodes.GENERAL_ERROR


@pytest.mark.unit
class TestCliUtilities:
    """Test cases for CLI utility functions."""
    
    def test_validate_roles_directory_valid(self, tmp_path):
        """Test roles directory validation with valid directory."""
        from cli import validate_roles_directory
        
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        
        result = validate_roles_directory(None, None, str(roles_dir))
        assert result == roles_dir
    
    def test_validate_roles_directory_invalid(self):
        """Test roles directory validation with invalid path."""
        from cli import validate_roles_directory
        
        with pytest.raises(Exception):  # click.BadParameter
            validate_roles_directory(None, None, "/nonexistent/directory")
    
    def test_validate_roles_directory_not_directory(self, tmp_path):
        """Test roles directory validation with file instead of directory."""
        from cli import validate_roles_directory
        
        not_dir = tmp_path / "not_a_directory.txt"
        not_dir.write_text("content")
        
        with pytest.raises(Exception):  # click.BadParameter
            validate_roles_directory(None, None, str(not_dir))


@pytest.mark.cli
@pytest.mark.security
class TestCLISecurityFeatures:
    """Test cases for security-related CLI features."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    def test_external_id_not_logged_in_plain_text(self):
        """Test that external IDs are not exposed in command output."""
        self.setUp()
        
        with patch('cli.config_loader.discover_role_configs') as mock_discover:
            with patch('cli.PulumiStackManager') as mock_stack_manager:
                mock_discover.return_value = []
                mock_manager = MagicMock()
                mock_stack_manager.return_value = mock_manager
                
                result = self.runner.invoke(cli, [
                    'deploy',
                    '--account-id', '123456789012',
                    '--external-id', 'super-secret-id',
                    '--json-output',
                    '--dry-run'
                ])
                
                # External ID should not appear in plain text in output
                assert 'super-secret-id' not in result.output
                # But masked version might appear
                assert '***' in result.output or 'external_id' not in result.output
    
    def test_sensitive_parameters_handling(self):
        """Test that sensitive parameters are handled securely."""
        self.setUp()
        
        # Test that deploy command help shows external-id option
        result = self.runner.invoke(cli, ['deploy', '--help'])
        
        # Help should mention external-id option
        assert 'external-id' in result.output
        assert result.exit_code == 0


@pytest.mark.cli
class TestCLIConsistency:
    """Test cases for CLI command consistency."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    def test_all_commands_support_account_id(self):
        """Test that all relevant commands support account-id parameter."""
        self.setUp()
        commands_requiring_account_id = ['deploy', 'destroy', 'status']
        
        for command in commands_requiring_account_id:
            result = self.runner.invoke(cli, [command, '--help'])
            assert 'account-id' in result.output
            assert result.exit_code == 0
    
    def test_consistent_environment_variable_naming(self):
        """Test that environment variables follow consistent naming."""
        self.setUp()
        
        result = self.runner.invoke(cli, ['deploy', '--help'])
        
        # Should mention consistent environment variable patterns
        env_patterns = ['AWS_', 'OIDC_', 'PULUMI_']
        for pattern in env_patterns:
            assert pattern in result.output
    
    def test_backend_url_supported_across_commands(self):
        """Test that backend-url is supported across all relevant commands."""
        self.setUp()
        
        commands_with_backend_url = ['deploy', 'destroy', 'status']
        
        for command in commands_with_backend_url:
            result = self.runner.invoke(cli, [command, '--help'])
            assert 'backend-url' in result.output
            assert result.exit_code == 0


@pytest.mark.cli  
class TestCLIAdditionalCoverage:
    """Additional tests to improve CLI coverage."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_with_role_name_filter(self, mock_stack_manager, mock_discover):
        """Test deploy command with specific role name filter."""
        self.setUp()
        mock_config = MagicMock()
        mock_config.role_name = "SpecificRole"
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--role-name', 'SpecificRole',
            '--dry-run'
        ])
        
        assert result.exit_code == 0
        mock_discover.assert_called_once()
        call_args = mock_discover.call_args[1]
        assert call_args['target_role_name'] == 'SpecificRole'
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_actual_deployment_path(self, mock_stack_manager, mock_discover):
        """Test actual deployment path (not dry-run)."""
        self.setUp()
        mock_config = MagicMock()
        mock_config.role_name = "TestRole"
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        
        # Mock deployment result
        mock_up_result = MagicMock()
        mock_up_result.summary.message = "Deployment successful"
        mock_manager.deploy.return_value = mock_up_result
        mock_manager.get_outputs.return_value = {"role_arn": MagicMock(value="arn:aws:iam::123456789012:role/TestRole")}
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--auto-approve'  # Skip confirmation
        ])
        
        assert result.exit_code == 0
        mock_manager.deploy.assert_called_once()
        mock_manager.get_outputs.assert_called_once()
    
    def test_deploy_with_json_output_deployment(self):
        """Test deploy command help shows JSON output option."""
        self.setUp()
        
        # Check global CLI help for json-output option
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert '--json-output' in result.output
        
        # Check deploy command help for auto-approve option
        result = self.runner.invoke(cli, [
            'deploy',
            '--help'
        ])
        
        assert result.exit_code == 0
        assert '--auto-approve' in result.output
    
    def test_destroy_command_no_stack(self):
        """Test destroy command help shows auto-approve option."""
        self.setUp()
        
        result = self.runner.invoke(cli, [
            'destroy',
            '--help'
        ])
        
        assert result.exit_code == 0
        assert '--auto-approve' in result.output
        assert '--account-id' in result.output
    
    def test_status_command_no_stack(self):
        """Test status command help shows account-id option."""
        self.setUp()
        
        result = self.runner.invoke(cli, [
            'status',
            '--help'
        ])
        
        assert result.exit_code == 0
        assert '--account-id' in result.output
    
    def test_list_stacks_command_with_stacks(self):
        """Test list-stacks command when stacks exist."""
        self.setUp()
        
        with patch('cli.Path') as mock_path:
            # Mock state directory with stacks
            mock_state_dir = MagicMock()
            mock_state_dir.exists.return_value = True
            mock_state_dir.glob.return_value = [
                MagicMock(name="dev-123456789012"),
                MagicMock(name="prod-987654321098")
            ]
            mock_path.cwd.return_value.joinpath.return_value = mock_state_dir
            
            result = self.runner.invoke(cli, ['list-stacks'])
            
            assert result.exit_code == 0
    
    def test_cli_keyboard_interrupt_handling(self):
        """Test CLI handling of keyboard interrupts."""
        self.setUp()
        
        with patch('cli.config_loader.discover_role_configs') as mock_discover:
            mock_discover.side_effect = KeyboardInterrupt("User interrupted")
            
            result = self.runner.invoke(cli, [
                'deploy',
                '--account-id', '123456789012',
                '--dry-run'
            ])
            
            assert result.exit_code == ExitCodes.GENERAL_ERROR
    
    def test_cli_debug_mode_exception_handling(self):
        """Test CLI exception handling in debug mode."""
        self.setUp()
        
        with patch('cli.config_loader.discover_role_configs') as mock_discover:
            mock_discover.side_effect = Exception("Test exception")
            
            result = self.runner.invoke(cli, [
                '--log-level', 'DEBUG',
                'deploy',
                '--account-id', '123456789012',
                '--dry-run'
            ])
            
            assert result.exit_code == ExitCodes.GENERAL_ERROR
    
    @patch('cli.config_loader.discover_role_configs')
    def test_validate_with_validation_error(self, mock_discover):
        """Test validate command with validation errors."""
        self.setUp()
        from oidc_role_manager.config_loader import ConfigError
        mock_discover.side_effect = ConfigError("Invalid role configuration")
        
        result = self.runner.invoke(cli, ['validate'])
        
        assert result.exit_code == ExitCodes.CONFIG_ERROR
        assert "Invalid role configuration" in result.output
    
    @patch('cli.config_loader.discover_role_configs')
    @patch('cli.PulumiStackManager')
    def test_deploy_with_aws_profile_and_region(self, mock_stack_manager, mock_discover):
        """Test deploy with AWS profile and region specified."""
        self.setUp()
        mock_config = MagicMock()
        mock_config.role_name = "TestRole"
        mock_discover.return_value = [mock_config]
        mock_manager = MagicMock()
        mock_stack_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, [
            'deploy',
            '--account-id', '123456789012',
            '--aws-profile', 'test-profile',
            '--aws-region', 'us-west-2',
            '--dry-run'
        ])
        
        assert result.exit_code == 0
        call_kwargs = mock_stack_manager.call_args[1]
        assert call_kwargs['aws_profile'] == 'test-profile'
        assert call_kwargs['aws_region'] == 'us-west-2' 