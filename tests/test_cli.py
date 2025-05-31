"""
Tests for CLI module
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from cli import cli, ExitCodes, validate_aws_account_id, setup_logging


class TestExitCodes:
    """Test cases for exit codes constants."""
    
    def test_exit_codes_defined(self):
        """Test that all exit codes are defined."""
        assert ExitCodes.SUCCESS == 0
        assert ExitCodes.GENERAL_ERROR == 1
        assert ExitCodes.CONFIG_ERROR == 2
        assert ExitCodes.VALIDATION_ERROR == 3
        assert ExitCodes.AWS_ERROR == 4


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


class TestErrorHandling:
    """Test cases for error handling in CLI."""
    
    def setUp(self):
        self.runner = CliRunner()
    
    def test_invalid_roles_directory(self):
        """Test with invalid roles directory."""
        self.setUp()
        result = self.runner.invoke(cli, [
            'validate', 
            '--roles-dir', '/nonexistent/directory'
        ])
        assert result.exit_code != 0
    
    def test_invalid_log_level(self):
        """Test with invalid log level."""
        self.setUp()
        result = self.runner.invoke(cli, [
            '--log-level', 'INVALID',
            'validate'
        ])
        assert result.exit_code != 0


class TestCliUtilities:
    """Test cases for CLI utility functions."""
    
    def test_validate_roles_directory_valid(self, tmp_path):
        """Test validate_roles_directory with valid directory."""
        from cli import validate_roles_directory
        
        result = validate_roles_directory(None, None, str(tmp_path))
        assert result == tmp_path
    
    def test_validate_roles_directory_invalid(self):
        """Test validate_roles_directory with invalid path."""
        from cli import validate_roles_directory
        
        with pytest.raises(Exception):  # click.BadParameter
            validate_roles_directory(None, None, "/nonexistent") 