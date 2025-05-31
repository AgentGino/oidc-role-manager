"""
Tests for constants module
"""

import pytest
from oidc_role_manager import constants


class TestDefaultTags:
    """Test cases for DEFAULT_TAGS constant."""
    
    def test_default_tags_exist(self):
        """Test that DEFAULT_TAGS is defined and has expected structure."""
        assert hasattr(constants, 'DEFAULT_TAGS')
        assert isinstance(constants.DEFAULT_TAGS, dict)
    
    def test_default_tags_required_keys(self):
        """Test that DEFAULT_TAGS contains expected keys."""
        required_keys = ["ManagedBy", "Environment", "Tool", "Purpose"]
        for key in required_keys:
            assert key in constants.DEFAULT_TAGS
    
    def test_default_tags_values(self):
        """Test that DEFAULT_TAGS contains expected values."""
        assert constants.DEFAULT_TAGS["ManagedBy"] == "OIDC-Role-Manager"
        assert constants.DEFAULT_TAGS["Tool"] == "Pulumi"
        assert constants.DEFAULT_TAGS["Purpose"] == "OIDC-GitHub-Integration"
        assert constants.DEFAULT_TAGS["Environment"] == "Development"
    
    def test_default_tags_immutability(self):
        """Test that modifying DEFAULT_TAGS doesn't affect original."""
        original_tags = constants.DEFAULT_TAGS.copy()
        
        # Modify a copy
        modified_tags = constants.DEFAULT_TAGS.copy()
        modified_tags["NewKey"] = "NewValue"
        
        # Original should be unchanged
        assert constants.DEFAULT_TAGS == original_tags


class TestOidcConfiguration:
    """Test cases for OIDC configuration constants."""
    
    def test_default_audience(self):
        """Test DEFAULT_AUDIENCE constant."""
        assert hasattr(constants, 'DEFAULT_AUDIENCE')
        assert constants.DEFAULT_AUDIENCE == "sts.amazonaws.com"
        assert isinstance(constants.DEFAULT_AUDIENCE, str)
    
    def test_github_oidc_provider_url(self):
        """Test GITHUB_OIDC_PROVIDER_URL constant."""
        assert hasattr(constants, 'GITHUB_OIDC_PROVIDER_URL')
        assert constants.GITHUB_OIDC_PROVIDER_URL == "token.actions.githubusercontent.com"
        assert isinstance(constants.GITHUB_OIDC_PROVIDER_URL, str)


class TestAwsResourceConfiguration:
    """Test cases for AWS resource configuration constants."""
    
    def test_max_inline_policies_per_role(self):
        """Test MAX_INLINE_POLICIES_PER_ROLE constant."""
        assert hasattr(constants, 'MAX_INLINE_POLICIES_PER_ROLE')
        assert constants.MAX_INLINE_POLICIES_PER_ROLE == 10
        assert isinstance(constants.MAX_INLINE_POLICIES_PER_ROLE, int)
        assert constants.MAX_INLINE_POLICIES_PER_ROLE > 0
    
    def test_max_managed_policies_per_role(self):
        """Test MAX_MANAGED_POLICIES_PER_ROLE constant."""
        assert hasattr(constants, 'MAX_MANAGED_POLICIES_PER_ROLE')
        assert constants.MAX_MANAGED_POLICIES_PER_ROLE == 20
        assert isinstance(constants.MAX_MANAGED_POLICIES_PER_ROLE, int)
        assert constants.MAX_MANAGED_POLICIES_PER_ROLE > 0


class TestValidationSettings:
    """Test cases for validation settings constants."""
    
    def test_valid_environments(self):
        """Test VALID_ENVIRONMENTS constant."""
        assert hasattr(constants, 'VALID_ENVIRONMENTS')
        assert isinstance(constants.VALID_ENVIRONMENTS, list)
        
        expected_environments = ["Development", "Staging", "Production", "Test"]
        assert constants.VALID_ENVIRONMENTS == expected_environments
        
        # Ensure all items are strings
        for env in constants.VALID_ENVIRONMENTS:
            assert isinstance(env, str)
    
    def test_required_role_fields(self):
        """Test REQUIRED_ROLE_FIELDS constant."""
        assert hasattr(constants, 'REQUIRED_ROLE_FIELDS')
        assert isinstance(constants.REQUIRED_ROLE_FIELDS, list)
        
        expected_fields = ["roleName", "oidcProviderUrl", "githubSubjectClaim"]
        assert constants.REQUIRED_ROLE_FIELDS == expected_fields
        
        # Ensure all items are strings
        for field in constants.REQUIRED_ROLE_FIELDS:
            assert isinstance(field, str)


class TestEnterpriseNamingPatterns:
    """Test cases for enterprise naming patterns constants."""
    
    def test_enterprise_naming_patterns_structure(self):
        """Test ENTERPRISE_NAMING_PATTERNS structure."""
        assert hasattr(constants, 'ENTERPRISE_NAMING_PATTERNS')
        assert isinstance(constants.ENTERPRISE_NAMING_PATTERNS, dict)
    
    def test_enterprise_naming_patterns_keys(self):
        """Test ENTERPRISE_NAMING_PATTERNS contains expected keys."""
        patterns = constants.ENTERPRISE_NAMING_PATTERNS
        
        expected_keys = ["role_prefix", "environment_tags", "max_role_name_length"]
        for key in expected_keys:
            assert key in patterns
    
    def test_enterprise_naming_patterns_values(self):
        """Test ENTERPRISE_NAMING_PATTERNS values are correct types."""
        patterns = constants.ENTERPRISE_NAMING_PATTERNS
        
        assert isinstance(patterns["role_prefix"], str)
        assert patterns["role_prefix"] == "GHA"
        
        assert isinstance(patterns["environment_tags"], list)
        expected_env_tags = ["Dev", "Staging", "Prod", "Test"]
        assert patterns["environment_tags"] == expected_env_tags
        
        assert isinstance(patterns["max_role_name_length"], int)
        assert patterns["max_role_name_length"] == 64
        assert patterns["max_role_name_length"] > 0


class TestConstantsIntegrity:
    """Test cases for overall constants integrity."""
    
    def test_no_none_values(self):
        """Test that no constants have None values."""
        for attr_name in dir(constants):
            if not attr_name.startswith('_'):  # Skip private attributes
                attr_value = getattr(constants, attr_name)
                if not callable(attr_value):  # Skip functions/methods
                    assert attr_value is not None, f"{attr_name} should not be None"
    
    def test_string_constants_not_empty(self):
        """Test that string constants are not empty."""
        string_constants = [
            'DEFAULT_AUDIENCE',
            'GITHUB_OIDC_PROVIDER_URL'
        ]
        
        for const_name in string_constants:
            if hasattr(constants, const_name):
                const_value = getattr(constants, const_name)
                if isinstance(const_value, str):
                    assert const_value.strip() != "", f"{const_name} should not be empty"
    
    def test_list_constants_not_empty(self):
        """Test that list constants are not empty."""
        list_constants = [
            'VALID_ENVIRONMENTS',
            'REQUIRED_ROLE_FIELDS'
        ]
        
        for const_name in list_constants:
            if hasattr(constants, const_name):
                const_value = getattr(constants, const_name)
                if isinstance(const_value, list):
                    assert len(const_value) > 0, f"{const_name} should not be empty"
    
    def test_numeric_constants_positive(self):
        """Test that numeric constants have positive values where expected."""
        numeric_constants = [
            'MAX_INLINE_POLICIES_PER_ROLE',
            'MAX_MANAGED_POLICIES_PER_ROLE'
        ]
        
        for const_name in numeric_constants:
            if hasattr(constants, const_name):
                const_value = getattr(constants, const_name)
                if isinstance(const_value, int):
                    assert const_value > 0, f"{const_name} should be positive"


class TestConstantsUsage:
    """Test cases for constants usage scenarios."""
    
    def test_default_tags_can_be_merged(self):
        """Test that DEFAULT_TAGS can be safely merged with other dicts."""
        custom_tags = {"Application": "TestApp", "Team": "DevOps"}
        
        # Should be able to merge without modifying original
        merged_tags = constants.DEFAULT_TAGS.copy()
        merged_tags.update(custom_tags)
        
        # Original should be unchanged
        assert "Application" not in constants.DEFAULT_TAGS
        assert "Team" not in constants.DEFAULT_TAGS
        
        # Merged should contain both
        assert "Application" in merged_tags
        assert "Team" in merged_tags
        assert "ManagedBy" in merged_tags
    
    def test_valid_environments_membership(self):
        """Test environment validation use case."""
        test_environments = ["Development", "Staging", "Production", "InvalidEnv"]
        
        for env in test_environments:
            is_valid = env in constants.VALID_ENVIRONMENTS
            if env == "InvalidEnv":
                assert not is_valid
            else:
                assert is_valid
    
    def test_required_fields_validation(self):
        """Test required fields validation use case."""
        test_config = {
            "roleName": "TestRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com",
            "githubSubjectClaim": "repo:org/repo:ref:refs/heads/main",
            "description": "Optional field"
        }
        
        # Should find all required fields
        missing_fields = [
            field for field in constants.REQUIRED_ROLE_FIELDS
            if field not in test_config
        ]
        assert len(missing_fields) == 0
        
        # Test with missing field
        incomplete_config = {
            "roleName": "TestRole",
            "oidcProviderUrl": "token.actions.githubusercontent.com"
            # Missing githubSubjectClaim
        }
        
        missing_fields = [
            field for field in constants.REQUIRED_ROLE_FIELDS
            if field not in incomplete_config
        ]
        assert "githubSubjectClaim" in missing_fields


class TestConstantsExportedValues:
    """Test that the expected constants are exported in the module."""
    
    def test_all_expected_constants_exist(self):
        """Test that all expected constants are defined."""
        expected_constants = [
            'DEFAULT_TAGS',
            'DEFAULT_AUDIENCE', 
            'GITHUB_OIDC_PROVIDER_URL',
            'MAX_INLINE_POLICIES_PER_ROLE',
            'MAX_MANAGED_POLICIES_PER_ROLE',
            'VALID_ENVIRONMENTS',
            'REQUIRED_ROLE_FIELDS',
            'ENTERPRISE_NAMING_PATTERNS'
        ]
        
        for const_name in expected_constants:
            assert hasattr(constants, const_name), f"Missing constant: {const_name}" 