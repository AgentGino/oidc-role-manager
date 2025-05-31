"""
Pulumi Automation API Manager
Handles programmatic Pulumi stack management and deployment
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pulumi
from pulumi import automation as auto
from rich.console import Console

from oidc_role_manager import iam_resources
from oidc_role_manager.config_loader import RoleConfig

logger = logging.getLogger(__name__)
console = Console()


class PulumiStackManager:
    """Manages Pulumi stack operations using the Automation API."""
    
    def __init__(self, project_name: str = "oidc-role-manager", 
                 stack_name: str = "dev", 
                 aws_region: Optional[str] = None,
                 aws_profile: Optional[str] = None,
                 backend_url: Optional[str] = None):
        self.project_name = project_name
        self.stack_name = stack_name
        self.aws_region = aws_region
        self.aws_profile = aws_profile
        self.work_dir = Path.cwd()
        
        # Use local file system backend by default for development
        if backend_url is None:
            self.backend_url = f"file://{self.work_dir / '.pulumi-state'}"
        else:
            self.backend_url = backend_url
        
        # Ensure state directory exists
        state_dir = self.work_dir / '.pulumi-state'
        state_dir.mkdir(exist_ok=True)
        
    def _create_pulumi_program(self, role_configs: List[RoleConfig]):
        """Create the Pulumi program function that defines all resources."""
        
        def pulumi_program():
            # Configure AWS provider if specified
            aws_provider = None
            if self.aws_region:
                import pulumi_aws as aws
                provider_opts = {"region": self.aws_region}
                if self.aws_profile:
                    provider_opts["profile"] = self.aws_profile
                
                aws_provider = aws.Provider(
                    f"aws-provider",
                    **provider_opts
                )
                logger.info(f"Configured AWS provider for region {self.aws_region}")
            
            # Create IAM resources for each role configuration
            created_roles = {}
            for config in role_configs:
                try:
                    role = iam_resources.create_iam_role_for_github_oidc(config, aws_provider)
                    created_roles[config.role_name] = role
                    logger.info(f"Defined resources for role: {config.role_name}")
                except Exception as e:
                    logger.error(f"Failed to define resources for role {config.role_name}: {e}")
                    raise
            
            # Export role information
            for role_name, role in created_roles.items():
                # Clean export name by removing common prefixes
                export_base = role_name.replace('GitHubAction', '').replace('Deploy', '')
                if not export_base:
                    export_base = role_name
                    
                pulumi.export(f"{export_base}_arn", role.arn)
                pulumi.export(f"{export_base}_name", role.name)
            
            return created_roles
        
        return pulumi_program
    
    def _get_stack_config(self) -> Dict[str, str]:
        """Get stack configuration."""
        config = {}
        
        # AWS configuration
        if self.aws_region:
            config["aws:region"] = self.aws_region
        if self.aws_profile:
            config["aws:profile"] = self.aws_profile
            
        return config
    
    def _create_workspace_settings(self) -> auto.LocalWorkspaceOptions:
        """Create workspace settings for local development."""
        return auto.LocalWorkspaceOptions(
            work_dir=str(self.work_dir),
            env_vars={
                # Use local backend
                "PULUMI_BACKEND_URL": self.backend_url,
                # Disable analytics for development
                "PULUMI_SKIP_UPDATE_CHECK": "true",
                # Set a default passphrase for local development
                "PULUMI_CONFIG_PASSPHRASE": os.getenv("PULUMI_CONFIG_PASSPHRASE", "dev-passphrase-123"),
            }
        )
    
    def preview_deployment(self, role_configs: List[RoleConfig]) -> auto.PreviewResult:
        """Preview the deployment without making changes."""
        logger.info("Creating deployment preview...")
        
        program = self._create_pulumi_program(role_configs)
        workspace_opts = self._create_workspace_settings()
        
        try:
            # Create or select stack with local backend
            stack = auto.create_or_select_stack(
                stack_name=self.stack_name,
                project_name=self.project_name,
                program=program,
                opts=workspace_opts
            )
            
            # Set configuration
            config = self._get_stack_config()
            for key, value in config.items():
                stack.set_config(key, auto.ConfigValue(value=value))
            
            # Refresh stack state
            logger.info("Refreshing stack state...")
            stack.refresh(on_output=self._output_handler)
            
            # Preview changes
            logger.info("Generating preview...")
            preview_result = stack.preview(on_output=self._output_handler)
            
            return preview_result
            
        except Exception as e:
            logger.error(f"Failed to create preview: {e}")
            raise
    
    def deploy(self, role_configs: List[RoleConfig]) -> auto.UpResult:
        """Deploy the resources to AWS."""
        logger.info("Starting deployment...")
        
        program = self._create_pulumi_program(role_configs)
        workspace_opts = self._create_workspace_settings()
        
        try:
            # Create or select stack with local backend
            stack = auto.create_or_select_stack(
                stack_name=self.stack_name,
                project_name=self.project_name,
                program=program,
                opts=workspace_opts
            )
            
            # Set configuration
            config = self._get_stack_config()
            for key, value in config.items():
                stack.set_config(key, auto.ConfigValue(value=value))
            
            # Refresh stack state
            logger.info("Refreshing stack state...")
            stack.refresh(on_output=self._output_handler)
            
            # Deploy
            logger.info("Applying changes...")
            up_result = stack.up(on_output=self._output_handler)
            
            logger.info("Deployment completed successfully!")
            
            # Store the stack for later use
            self._current_stack = stack
            
            return up_result
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            raise
    
    def destroy(self) -> auto.DestroyResult:
        """Destroy all resources in the stack."""
        logger.warning("Starting resource destruction...")
        
        # Create a minimal program for destruction
        def empty_program():
            pass
        
        workspace_opts = self._create_workspace_settings()
        
        try:
            # Create or select stack with local backend (same pattern as deploy)
            stack = auto.create_or_select_stack(
                stack_name=self.stack_name,
                project_name=self.project_name,
                program=empty_program,
                opts=workspace_opts
            )
            
            # Set configuration
            config = self._get_stack_config()
            for key, value in config.items():
                stack.set_config(key, auto.ConfigValue(value=value))
            
            # Destroy resources
            destroy_result = stack.destroy(on_output=self._output_handler)
            
            logger.info("Resources destroyed successfully!")
            return destroy_result
            
        except Exception as e:
            logger.error(f"Destruction failed: {e}")
            raise
    
    def get_outputs(self) -> Dict[str, auto.OutputValue]:
        """Get stack outputs."""
        # Use stored stack from recent deployment if available
        if hasattr(self, '_current_stack') and self._current_stack:
            try:
                return self._current_stack.outputs()
            except Exception as e:
                logger.debug(f"Failed to get outputs from current stack: {e}")
        
        # Fallback to creating new stack connection
        def empty_program():
            pass
            
        workspace_opts = self._create_workspace_settings()
        
        try:
            # Create or select stack with local backend (same pattern as deploy)
            stack = auto.create_or_select_stack(
                stack_name=self.stack_name,
                project_name=self.project_name,
                program=empty_program,
                opts=workspace_opts
            )
            
            return stack.outputs()
            
        except Exception as e:
            logger.error(f"Failed to get outputs: {e}")
            raise
    
    def get_stack_info(self) -> Optional[auto.StackSummary]:
        """Get stack information."""
        def empty_program():
            pass
            
        workspace_opts = self._create_workspace_settings()
        
        try:
            # Create or select stack with local backend (same pattern as deploy)
            stack = auto.create_or_select_stack(
                stack_name=self.stack_name,
                project_name=self.project_name,
                program=empty_program,
                opts=workspace_opts
            )
            
            return stack.info()
            
        except Exception as e:
            logger.debug(f"Stack not found or error getting info: {e}")
            return None
    
    def _output_handler(self, output: str) -> None:
        """Handle Pulumi output for logging."""
        # Filter out noisy log messages
        if any(skip in output for skip in ['Downloading', 'Installing', 'diagnostic:']):
            return
            
        # Log important messages
        if any(keyword in output for keyword in ['error:', 'Error:', 'failed', 'Failed']):
            logger.error(f"Pulumi: {output.strip()}")
        elif any(keyword in output for keyword in ['warning:', 'Warning:']):
            logger.warning(f"Pulumi: {output.strip()}")
        else:
            logger.debug(f"Pulumi: {output.strip()}") 