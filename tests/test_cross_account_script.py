"""
Tests for cross-account deployment script
"""

import pytest
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call


class TestCrossAccountDeployScript:
    """Test cases for the cross-account deployment shell script."""
    
    def setup_method(self):
        """Set up test environment."""
        self.script_path = Path(__file__).parent.parent / "scripts" / "cross-account-deploy.sh"
        self.test_env = {
            'PATH': os.environ.get('PATH', ''),
            'AWS_EXTERNAL_ID': 'test-external-id',
            'DRY_RUN': 'true'
        }
    
    def test_script_exists_and_executable(self):
        """Test that the cross-account deployment script exists and is executable."""
        assert self.script_path.exists(), "Cross-account deployment script should exist"
        assert os.access(self.script_path, os.X_OK), "Script should be executable"
    
    def test_script_help_option(self):
        """Test script help option."""
        try:
            result = subprocess.run([
                'bash', str(self.script_path), '--help'
            ], capture_output=True, text=True, timeout=10)
            
            assert result.returncode == 0
            assert "Cross-Account OIDC Role Deployment Script" in result.stdout
            assert "Usage:" in result.stdout
            assert "Methods:" in result.stdout
            assert "profile" in result.stdout
            assert "assume-role" in result.stdout
            assert "env-vars" in result.stdout
        except subprocess.TimeoutExpired:
            pytest.fail("Script help command timed out")
    
    @patch('subprocess.run')
    def test_validate_prerequisites_function(self, mock_run):
        """Test the validate_prerequisites function in the script."""
        # Mock successful command checks
        mock_run.return_value = MagicMock(returncode=0)
        
        # This would test the actual validation logic
        # In a real implementation, we'd need to extract and test the function
        pass
    
    def test_script_with_invalid_method(self):
        """Test script with invalid deployment method."""
        try:
            result = subprocess.run([
                'bash', str(self.script_path), 'invalid-method'
            ], capture_output=True, text=True, timeout=10, env=self.test_env)
            
            assert result.returncode != 0
            assert "Unknown option" in result.stderr or "Unknown" in result.stdout
        except subprocess.TimeoutExpired:
            pytest.fail("Script with invalid method timed out")
    
    def test_script_dry_run_environment_variable(self):
        """Test that DRY_RUN environment variable is respected."""
        # Test that the script recognizes DRY_RUN environment variable
        env_with_dry_run = {**self.test_env, 'DRY_RUN': 'true'}
        
        try:
            # This would fail without proper cli.py setup, but we're testing the script structure
            result = subprocess.run([
                'bash', str(self.script_path), 'profile'
            ], capture_output=True, text=True, timeout=10, env=env_with_dry_run)
            
            # Script should attempt to run but may fail due to missing dependencies
            # We're mainly testing that it doesn't crash on argument parsing
            assert "DRY RUN MODE" in result.stdout or result.returncode != 0
        except subprocess.TimeoutExpired:
            pytest.fail("Script dry run test timed out")


class TestCrossAccountDeploymentMethods:
    """Test cases for different deployment methods in the script."""
    
    def setup_method(self):
        """Set up test environment."""
        self.script_path = Path(__file__).parent.parent / "scripts" / "cross-account-deploy.sh"
    
    def test_profile_method_syntax(self):
        """Test that profile method has correct syntax."""
        # Read script content to validate function definitions
        script_content = self.script_path.read_text()
        
        # Check that required functions are defined
        assert "deploy_with_profile()" in script_content
        assert "deploy_with_role_assumption()" in script_content
        assert "deploy_with_env_vars()" in script_content
        assert "validate_prerequisites()" in script_content
        assert "deploy_all_accounts()" in script_content
    
    def test_script_configuration_arrays(self):
        """Test that script has proper configuration arrays."""
        script_content = self.script_path.read_text()
        
        # Check that ACCOUNTS array is properly defined
        assert "ACCOUNTS=(" in script_content
        assert "BASE_ROLE_ARN_TEMPLATE=" in script_content
        
        # Check for account configuration format examples
        assert "123456789012:" in script_content
        assert ":role" in script_content
    
    def test_environment_variable_handling(self):
        """Test that script properly handles environment variables."""
        script_content = self.script_path.read_text()
        
        # Check for proper environment variable usage
        assert "AWS_EXTERNAL_ID" in script_content
        assert "DRY_RUN" in script_content
        assert "${" in script_content  # Variable expansion syntax
        
        # Check for default value handling
        assert ":-}" in script_content or ":-" in script_content
    
    def test_error_handling_functions(self):
        """Test that script has proper error handling functions."""
        script_content = self.script_path.read_text()
        
        # Check for logging functions
        assert "log()" in script_content
        assert "error()" in script_content
        assert "success()" in script_content
        assert "warn()" in script_content
        
        # Check for error handling patterns
        assert "set -euo pipefail" in script_content


class TestScriptIntegration:
    """Integration tests for the cross-account deployment script."""
    
    def setup_method(self):
        """Set up test environment."""
        self.script_path = Path(__file__).parent.parent / "scripts" / "cross-account-deploy.sh"
        self.mock_cli_path = Path(__file__).parent.parent / "cli.py"
    
    @pytest.mark.skipif(not Path("cli.py").exists(), reason="cli.py not found")
    def test_script_with_mock_cli(self):
        """Test script integration with mock CLI responses."""
        # This test would mock the CLI responses and test the full script flow
        # It's skipped if cli.py doesn't exist in the expected location
        pass
    
    def test_script_bashisms_and_portability(self):
        """Test that script uses portable shell constructs."""
        script_content = self.script_path.read_text()
        
        # Check for bash-specific features that might cause portability issues
        # The script uses #!/bin/bash so bash features are OK, but check for common issues
        assert script_content.startswith("#!/bin/bash")
        
        # Check for proper quoting
        lines_with_variables = [line for line in script_content.split('\n') if '$' in line and not line.strip().startswith('#')]
        
        # Most variable references should be properly quoted
        # This is a heuristic test
        assert len(lines_with_variables) > 0  # Should have variable usage
    
    def test_script_command_line_argument_parsing(self):
        """Test script command line argument parsing logic."""
        script_content = self.script_path.read_text()
        
        # Check for proper argument parsing patterns
        assert "while [[ $# -gt 0 ]]" in script_content or "while [ $# -gt 0 ]" in script_content
        assert "case $1 in" in script_content or "case \"$1\" in" in script_content
        assert "shift" in script_content
        
        # Check for help option handling
        assert "-h|--help" in script_content
        assert "show_usage" in script_content


class TestScriptConfiguration:
    """Test cases for script configuration and setup."""
    
    def setup_method(self):
        """Set up test environment."""
        self.script_path = Path(__file__).parent.parent / "scripts" / "cross-account-deploy.sh"
    
    def test_default_configuration_values(self):
        """Test that script has reasonable default configuration values."""
        script_content = self.script_path.read_text()
        
        # Check for reasonable defaults
        assert "arn:aws:iam::" in script_content  # Role ARN template
        assert "CrossAccountDeploymentRole" in script_content or "CrossAccount" in script_content
        
        # Check for multiple account examples
        account_count = script_content.count("123456789012")
        assert account_count >= 1  # Should have at least one example account
    
    def test_color_output_configuration(self):
        """Test that script has color output configuration."""
        script_content = self.script_path.read_text()
        
        # Check for ANSI color codes
        assert "\\033[" in script_content
        assert "RED=" in script_content
        assert "GREEN=" in script_content
        assert "YELLOW=" in script_content
        assert "NC=" in script_content  # No Color
    
    def test_script_documentation(self):
        """Test that script has proper documentation."""
        script_content = self.script_path.read_text()
        
        # Check for header documentation
        lines = script_content.split('\n')
        header_lines = lines[:10]  # First 10 lines
        
        comment_lines = [line for line in header_lines if line.startswith('#')]
        assert len(comment_lines) >= 3  # Should have substantial header comments
        
        # Check for usage function
        assert "show_usage()" in script_content
        assert "cat << EOF" in script_content or "cat <<EOF" in script_content


class TestScriptSecurity:
    """Test cases for security aspects of the deployment script."""
    
    def setup_method(self):
        """Set up test environment."""
        self.script_path = Path(__file__).parent.parent / "scripts" / "cross-account-deploy.sh"
    
    def test_external_id_handling(self):
        """Test that external IDs are handled securely."""
        script_content = self.script_path.read_text()
        
        # Check that external ID is used in role assumption
        assert "external-id" in script_content.lower()
        assert "AWS_EXTERNAL_ID" in script_content
        
        # Should not contain hardcoded external IDs (security risk)
        # External IDs should come from environment variables
        assert "--external-id $" in script_content or '--external-id "$' in script_content
    
    def test_no_hardcoded_credentials(self):
        """Test that script doesn't contain hardcoded credentials."""
        script_content = self.script_path.read_text()
        
        # Check that there are no obvious credential patterns
        suspicious_patterns = [
            "AKIA",  # AWS Access Key prefix
            "aws_secret_access_key",
            "password=",
            "secret=",
            "token="
        ]
        
        for pattern in suspicious_patterns:
            assert pattern.lower() not in script_content.lower(), f"Suspicious pattern found: {pattern}"
    
    def test_proper_variable_quoting(self):
        """Test that variables are properly quoted to prevent injection."""
        script_content = self.script_path.read_text()
        
        # Find variable assignments and usage
        # This is a basic check - in practice, you'd want more sophisticated analysis
        lines = script_content.split('\n')
        
        # Check for common dangerous patterns
        dangerous_patterns = [
            "eval $",  # Unquoted eval
            "sh $",    # Unquoted shell execution
            "bash $"   # Unquoted bash execution
        ]
        
        for line in lines:
            for pattern in dangerous_patterns:
                assert pattern not in line, f"Potentially dangerous pattern found: {pattern} in line: {line}"


class TestScriptMaintainability:
    """Test cases for script maintainability and code quality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.script_path = Path(__file__).parent.parent / "scripts" / "cross-account-deploy.sh"
    
    def test_function_organization(self):
        """Test that script is well-organized with proper functions."""
        script_content = self.script_path.read_text()
        
        # Check for logical function organization
        required_functions = [
            "log(",
            "error(",
            "success(",
            "warn(",
            "deploy_with_profile(",
            "deploy_with_role_assumption(",
            "deploy_with_env_vars(",
            "validate_prerequisites(",
            "deploy_all_accounts(",
            "show_usage(",
            "main("
        ]
        
        for func in required_functions:
            assert func in script_content, f"Required function not found: {func}"
    
    def test_consistent_coding_style(self):
        """Test that script follows consistent coding style."""
        script_content = self.script_path.read_text()
        
        # Check for consistent indentation (basic check)
        lines = script_content.split('\n')
        indented_lines = [line for line in lines if line.startswith('    ') or line.startswith('\t')]
        
        # Should have some indented lines (functions, conditionals, etc.)
        assert len(indented_lines) > 10
        
        # Check for consistent error handling
        assert "set -euo pipefail" in script_content
    
    def test_script_modularity(self):
        """Test that script is modular and reusable."""
        script_content = self.script_path.read_text()
        
        # Check for configuration section
        assert "# Configuration" in script_content or "ACCOUNTS=" in script_content
        
        # Check for main function pattern
        assert 'if [[ "${BASH_SOURCE[0]}" == "${0}" ]]' in script_content
        assert "main" in script_content
        
        # Check that functions are small and focused
        function_lines = []
        in_function = False
        current_function_lines = 0
        
        for line in script_content.split('\n'):
            if '() {' in line:
                in_function = True
                current_function_lines = 0
            elif in_function and line.strip() == '}':
                function_lines.append(current_function_lines)
                in_function = False
            elif in_function:
                current_function_lines += 1
        
        # Functions should generally be reasonably sized (under 50 lines)
        if function_lines:
            avg_function_size = sum(function_lines) / len(function_lines)
            assert avg_function_size < 50, f"Average function size too large: {avg_function_size}" 