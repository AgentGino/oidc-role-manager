"""
Tests for config_loader module
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from oidc_role_manager.config_loader import (
    ConfigError,
    RoleConfig,
    _load_json_file,
    load_role_config,
    discover_role_configs,
)


class TestConfigError:
    """Test cases for ConfigError exception."""
    
    def test_config_error_inheritance(self):
        """Test that ConfigError inherits from Exception."""
        assert issubclass(ConfigError, Exception)
    
    def test_config_error_message(self):
        """Test ConfigError with custom message."""
        error = ConfigError("Test error message")
        assert str(error) == "Test error message"


class TestRoleConfig:
    """Test cases for RoleConfig class."""
    
    def test_role_config_initialization(self):
        """Test RoleConfig initialization."""
        details = {"roleName": "TestRole", "description": "Test role"}
        managed_policies = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]
        inline_policies = {"policy1": {"Version": "2012-10-17"}}
        
        config = RoleConfig(
            account_id="123456789012",
            role_name_dir="TestRole",
            details=details,
            managed_policies=managed_policies,
            inline_policies=inline_policies,
            base_dir="/path/to/roles"
        )
        
        assert config.account_id == "123456789012"
        assert config.role_name_dir == "TestRole"
        assert config.details == details
        assert config.managed_policies == managed_policies
        assert config.inline_policies == inline_policies
        assert config.path == "/path/to/roles/123456789012/TestRole"
    
    def test_role_name_property(self):
        """Test role_name property."""
        details = {"roleName": "MyTestRole"}
        config = RoleConfig("123456789012", "TestRole", details, [], {}, "/base")
        assert config.role_name == "MyTestRole"
    
    def test_role_name_property_missing(self):
        """Test role_name property when roleName is missing."""
        details = {}
        config = RoleConfig("123456789012", "TestRole", details, [], {}, "/base")
        assert config.role_name is None
    
    def test_str_representation(self):
        """Test string representation of RoleConfig."""
        details = {"roleName": "MyTestRole"}
        config = RoleConfig("123456789012", "TestRole", details, [], {}, "/base")
        expected = "RoleConfig(account_id=123456789012, role_name_dir=TestRole, name=MyTestRole)"
        assert str(config) == expected


class TestLoadJsonFile:
    """Test cases for _load_json_file function."""
    
    def test_load_json_file_success_dict(self, tmp_path):
        """Test successful loading of JSON dict."""
        json_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 123}
        json_file.write_text(json.dumps(test_data))
        
        result = _load_json_file(str(json_file))
        assert result == test_data
    
    def test_load_json_file_success_list(self, tmp_path):
        """Test successful loading of JSON list."""
        json_file = tmp_path / "test.json"
        test_data = ["item1", "item2", 123]
        json_file.write_text(json.dumps(test_data))
        
        result = _load_json_file(str(json_file), is_list=True)
        assert result == test_data
    
    def test_load_json_file_not_found_required(self):
        """Test loading non-existent required file raises error."""
        with pytest.raises(ConfigError, match="Required config file not found"):
            _load_json_file("/nonexistent/file.json")
    
    def test_load_json_file_not_found_optional_dict(self):
        """Test loading non-existent optional file returns empty dict."""
        result = _load_json_file("/nonexistent/file.json", optional=True)
        assert result == {}
    
    def test_load_json_file_not_found_optional_list(self):
        """Test loading non-existent optional file returns empty list."""
        result = _load_json_file("/nonexistent/file.json", is_list=True, optional=True)
        assert result == []
    
    def test_load_json_file_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises error."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{ invalid json }")
        
        with pytest.raises(ConfigError, match="Error decoding JSON"):
            _load_json_file(str(json_file))
    
    def test_load_json_file_wrong_type_expected_list(self, tmp_path):
        """Test loading dict when list expected raises error."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')
        
        with pytest.raises(ConfigError, match="is not a valid JSON list"):
            _load_json_file(str(json_file), is_list=True)
    
    def test_load_json_file_wrong_type_expected_dict(self, tmp_path):
        """Test loading list when dict expected raises error."""
        json_file = tmp_path / "test.json"
        json_file.write_text('["item1", "item2"]')
        
        with pytest.raises(ConfigError, match="is not a valid JSON object"):
            _load_json_file(str(json_file), is_list=False)
    
    @patch("builtins.open")
    @patch("os.path.exists")
    def test_load_json_file_read_error(self, mock_exists, mock_open_func):
        """Test handling of file read errors."""
        mock_exists.return_value = True  # File exists
        mock_open_func.side_effect = IOError("Permission denied")
        
        with pytest.raises(ConfigError, match="Error reading file"):
            _load_json_file("/some/file.json")


class TestLoadRoleConfig:
    """Test cases for load_role_config function."""
    
    def test_load_role_config_success(self, tmp_path):
        """Test successful role config loading."""
        # Setup test directory structure
        role_dir = tmp_path / "123456789012" / "TestRole"
        role_dir.mkdir(parents=True)
        
        # Create details.json
        details = {
            "roleName": "TestRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main",
            "description": "Test role"
        }
        (role_dir / "details.json").write_text(json.dumps(details))
        
        # Create managed-policies.json
        managed_policies = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]
        (role_dir / "managed-policies.json").write_text(json.dumps(managed_policies))
        
        # Create inline policy
        inline_policy = {"Version": "2012-10-17", "Statement": []}
        (role_dir / "inline-TestPolicy.json").write_text(json.dumps(inline_policy))
        
        config = load_role_config(str(tmp_path), "123456789012", "TestRole")
        
        assert config.account_id == "123456789012"
        assert config.role_name_dir == "TestRole"
        assert config.role_name == "TestRole"
        assert config.details == details
        assert config.managed_policies == managed_policies
        assert "inline-TestPolicy.json" in config.inline_policies
        assert config.inline_policies["inline-TestPolicy.json"] == inline_policy
    
    def test_load_role_config_missing_directory(self, tmp_path):
        """Test loading config from non-existent directory."""
        with pytest.raises(ConfigError, match="Role directory not found"):
            load_role_config(str(tmp_path), "123456789012", "NonExistentRole")
    
    def test_load_role_config_missing_details_file(self, tmp_path):
        """Test loading config with missing details.json."""
        role_dir = tmp_path / "123456789012" / "TestRole"
        role_dir.mkdir(parents=True)
        
        with pytest.raises(ConfigError, match="Required config file not found"):
            load_role_config(str(tmp_path), "123456789012", "TestRole")
    
    def test_load_role_config_missing_required_fields(self, tmp_path):
        """Test loading config with missing required fields in details.json."""
        role_dir = tmp_path / "123456789012" / "TestRole"
        role_dir.mkdir(parents=True)
        
        # Missing required fields
        details = {"roleName": "TestRole"}  # Missing oidcProviderUrl and githubSubjectClaim
        (role_dir / "details.json").write_text(json.dumps(details))
        
        with pytest.raises(ConfigError, match="Missing required fields"):
            load_role_config(str(tmp_path), "123456789012", "TestRole")
    
    def test_load_role_config_no_managed_policies(self, tmp_path):
        """Test loading config without managed policies file."""
        role_dir = tmp_path / "123456789012" / "TestRole"
        role_dir.mkdir(parents=True)
        
        details = {
            "roleName": "TestRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
        }
        (role_dir / "details.json").write_text(json.dumps(details))
        
        config = load_role_config(str(tmp_path), "123456789012", "TestRole")
        
        assert config.managed_policies == []
    
    def test_load_role_config_invalid_inline_policy(self, tmp_path, caplog):
        """Test loading config with invalid inline policy."""
        role_dir = tmp_path / "123456789012" / "TestRole"
        role_dir.mkdir(parents=True)
        
        details = {
            "roleName": "TestRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
        }
        (role_dir / "details.json").write_text(json.dumps(details))
        
        # Create invalid inline policy
        (role_dir / "inline-BadPolicy.json").write_text("{ invalid json }")
        
        config = load_role_config(str(tmp_path), "123456789012", "TestRole")
        
        # Should load successfully but skip the invalid policy
        assert config.role_name == "TestRole"
        assert "inline-BadPolicy.json" not in config.inline_policies
        assert "Could not load inline policy" in caplog.text
    
    def test_load_role_config_multiple_inline_policies(self, tmp_path):
        """Test loading config with multiple inline policies."""
        role_dir = tmp_path / "123456789012" / "TestRole"
        role_dir.mkdir(parents=True)
        
        details = {
            "roleName": "TestRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
        }
        (role_dir / "details.json").write_text(json.dumps(details))
        
        # Create multiple inline policies
        policy1 = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]}
        policy2 = {"Version": "2012-10-17", "Statement": [{"Effect": "Deny"}]}
        
        (role_dir / "inline-Policy1.json").write_text(json.dumps(policy1))
        (role_dir / "inline-Policy2.json").write_text(json.dumps(policy2))
        
        config = load_role_config(str(tmp_path), "123456789012", "TestRole")
        
        assert len(config.inline_policies) == 2
        assert "inline-Policy1.json" in config.inline_policies
        assert "inline-Policy2.json" in config.inline_policies
        assert config.inline_policies["inline-Policy1.json"] == policy1
        assert config.inline_policies["inline-Policy2.json"] == policy2


class TestDiscoverRoleConfigs:
    """Test cases for discover_role_configs function."""
    
    def test_discover_role_configs_success(self, tmp_path):
        """Test successful discovery of role configurations."""
        # Setup test directory structure
        account_dir = tmp_path / "123456789012"
        account_dir.mkdir()
        
        # Create first role
        role1_dir = account_dir / "Role1"
        role1_dir.mkdir()
        details1 = {
            "roleName": "Role1",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
        }
        (role1_dir / "details.json").write_text(json.dumps(details1))
        
        # Create second role
        role2_dir = account_dir / "Role2"
        role2_dir.mkdir()
        details2 = {
            "roleName": "Role2",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:environment:prod"
        }
        (role2_dir / "details.json").write_text(json.dumps(details2))
        
        configs = discover_role_configs(str(tmp_path), "123456789012")
        
        assert len(configs) == 2
        role_names = [config.role_name for config in configs]
        assert "Role1" in role_names
        assert "Role2" in role_names
    
    def test_discover_role_configs_missing_account_directory(self, tmp_path):
        """Test discovery with missing account directory."""
        configs = discover_role_configs(str(tmp_path), "999999999999")
        assert configs == []
    
    def test_discover_role_configs_empty_account_directory(self, tmp_path):
        """Test discovery with empty account directory."""
        account_dir = tmp_path / "123456789012"
        account_dir.mkdir()
        
        configs = discover_role_configs(str(tmp_path), "123456789012")
        assert configs == []
    
    def test_discover_role_configs_specific_role(self, tmp_path):
        """Test discovery of specific role."""
        account_dir = tmp_path / "123456789012"
        account_dir.mkdir()
        
        # Create target role
        target_role_dir = account_dir / "TargetRole"
        target_role_dir.mkdir()
        details = {
            "roleName": "TargetRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
        }
        (target_role_dir / "details.json").write_text(json.dumps(details))
        
        # Create other role
        other_role_dir = account_dir / "OtherRole"
        other_role_dir.mkdir()
        
        configs = discover_role_configs(str(tmp_path), "123456789012", "TargetRole")
        
        assert len(configs) == 1
        assert configs[0].role_name == "TargetRole"
    
    def test_discover_role_configs_specific_role_not_found(self, tmp_path):
        """Test discovery of non-existent specific role."""
        account_dir = tmp_path / "123456789012"
        account_dir.mkdir()
        
        configs = discover_role_configs(str(tmp_path), "123456789012", "NonExistentRole")
        assert configs == []
    
    def test_discover_role_configs_invalid_role_skipped(self, tmp_path, caplog):
        """Test discovery skips invalid role configurations."""
        account_dir = tmp_path / "123456789012"
        account_dir.mkdir()
        
        # Create valid role
        valid_role_dir = account_dir / "ValidRole"
        valid_role_dir.mkdir()
        valid_details = {
            "roleName": "ValidRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
        }
        (valid_role_dir / "details.json").write_text(json.dumps(valid_details))
        
        # Create invalid role (missing required fields)
        invalid_role_dir = account_dir / "InvalidRole"
        invalid_role_dir.mkdir()
        invalid_details = {"roleName": "InvalidRole"}  # Missing required fields
        (invalid_role_dir / "details.json").write_text(json.dumps(invalid_details))
        
        configs = discover_role_configs(str(tmp_path), "123456789012")
        
        # Should only return the valid role
        assert len(configs) == 1
        assert configs[0].role_name == "ValidRole"
        
        # Should log error for invalid role
        assert "Failed to load configuration for role directory 'InvalidRole'" in caplog.text
    
    def test_discover_role_configs_handles_files_in_account_dir(self, tmp_path):
        """Test discovery ignores files in account directory."""
        account_dir = tmp_path / "123456789012"
        account_dir.mkdir()
        
        # Create a file (should be ignored)
        (account_dir / "somefile.txt").write_text("content")
        
        # Create valid role directory
        role_dir = account_dir / "ValidRole"
        role_dir.mkdir()
        details = {
            "roleName": "ValidRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main"
        }
        (role_dir / "details.json").write_text(json.dumps(details))
        
        configs = discover_role_configs(str(tmp_path), "123456789012")
        
        assert len(configs) == 1
        assert configs[0].role_name == "ValidRole" 