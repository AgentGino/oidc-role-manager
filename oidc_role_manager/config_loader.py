import os
import json
import logging

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Custom exception for configuration loading errors."""
    pass

class RoleConfig:
    """Represents the fully loaded configuration for a single IAM role."""
    def __init__(self, account_id: str, role_name_dir: str, details: dict, 
                 managed_policies: list, inline_policies: dict, base_dir: str):
        self.account_id = account_id
        self.role_name_dir = role_name_dir # The directory name for the role, e.g., "DeployToStaging"
        self.details = details
        self.managed_policies = managed_policies
        self.inline_policies = inline_policies
        self.path = os.path.join(base_dir, account_id, role_name_dir)

    @property
    def role_name(self) -> str:
        return self.details.get('roleName')

    def __str__(self):
        return f"RoleConfig(account_id={self.account_id}, role_name_dir={self.role_name_dir}, name={self.role_name})"

def _load_json_file(file_path: str, is_list: bool = False, optional: bool = False):
    """Helper to load and validate a JSON file."""
    if not os.path.exists(file_path):
        if optional:
            logger.debug(f"Optional config file not found: {file_path}")
            return [] if is_list else {}
        raise ConfigError(f"Required config file not found: {file_path}")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        if is_list and not isinstance(data, list):
            raise ConfigError(f"Config file {file_path} is not a valid JSON list.")
        if not is_list and not isinstance(data, dict):
             raise ConfigError(f"Config file {file_path} is not a valid JSON object.")
        logger.debug(f"Successfully loaded config file: {file_path}")
        return data
    except json.JSONDecodeError as e:
        raise ConfigError(f"Error decoding JSON from {file_path}: {e}")
    except Exception as e:
        raise ConfigError(f"Error reading file {file_path}: {e}")

def load_role_config(base_roles_dir: str, account_id: str, role_name_dir: str) -> RoleConfig:
    """Loads the configuration for a single specified role."""
    logger.info(f"Loading configuration for role '{role_name_dir}' in account '{account_id}' from '{base_roles_dir}'.")
    role_dir_path = os.path.join(base_roles_dir, account_id, role_name_dir)

    if not os.path.isdir(role_dir_path):
        raise ConfigError(f"Role directory not found: {role_dir_path}")

    details_file = os.path.join(role_dir_path, "details.json")
    managed_policies_file = os.path.join(role_dir_path, "managed-policies.json")

    details_data = _load_json_file(details_file)
    # Basic validation for required fields in details.json
    required_details_fields = ['roleName', 'oidcProviderUrl', 'githubSubjectClaim']
    missing_fields = [field for field in required_details_fields if field not in details_data]
    if missing_fields:
        raise ConfigError(f"Missing required fields in '{details_file}': {missing_fields}")

    managed_policies_data = _load_json_file(managed_policies_file, is_list=True, optional=True)
    
    inline_policies_data = {}
    for item_name in os.listdir(role_dir_path):
        if item_name.startswith("inline-") and item_name.endswith(".json"):
            inline_policy_file_path = os.path.join(role_dir_path, item_name)
            try:
                policy_doc = _load_json_file(inline_policy_file_path)
                inline_policies_data[item_name] = policy_doc # Storing filename as key
            except ConfigError as e:
                logger.warning(f"Could not load inline policy '{item_name}': {e}. Skipping this policy.")
                # Continue loading other policies even if one fails, but log a warning.

    return RoleConfig(account_id, role_name_dir, details_data, managed_policies_data, inline_policies_data, base_roles_dir)

def discover_role_configs(base_roles_dir: str, target_account_id: str, target_role_name: str = None) -> list[RoleConfig]:
    """Discovers and loads role configurations for a given account, optionally filtered by a specific role name."""
    logger.info(f"Discovering role configurations in '{base_roles_dir}' for account '{target_account_id}'.")
    account_dir_path = os.path.join(base_roles_dir, target_account_id)

    if not os.path.isdir(account_dir_path):
        logger.error(f"Account directory not found: {account_dir_path}")
        return []

    role_configs = []
    role_name_dirs_to_process = []

    if target_role_name:
        # If a specific role name is targeted, only process that directory.
        target_role_path = os.path.join(account_dir_path, target_role_name)
        if os.path.isdir(target_role_path):
            role_name_dirs_to_process.append(target_role_name)
        else:
            logger.error(f"Specified role directory '{target_role_name}' not found in '{account_dir_path}'.")
            return [] # Or raise an error, depending on desired CLI behavior.
    else:
        # Process all role directories under the account.
        for role_name_candidate in os.listdir(account_dir_path):
            if os.path.isdir(os.path.join(account_dir_path, role_name_candidate)):
                role_name_dirs_to_process.append(role_name_candidate)

    if not role_name_dirs_to_process:
        logger.warning(f"No role directories found to process in '{account_dir_path}'.")
        return []

    for role_name_dir in role_name_dirs_to_process:
        try:
            config = load_role_config(base_roles_dir, target_account_id, role_name_dir)
            role_configs.append(config)
            logger.info(f"Successfully loaded configuration for: {config.role_name}")
        except ConfigError as e:
            logger.error(f"Failed to load configuration for role directory '{role_name_dir}' in account '{target_account_id}': {e}")
            # Decide if one bad config should stop all, or just skip this one. For now, skipping.
        except Exception as e:
            logger.error(f"An unexpected error occurred loading role '{role_name_dir}': {e}")
            
    return role_configs 