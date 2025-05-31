#!/usr/bin/env python3
"""
Enterprise OIDC Role Manager CLI
Manages AWS IAM OIDC roles for GitHub Actions using Pulumi
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from oidc_role_manager import config_loader
from oidc_role_manager.pulumi_manager import PulumiStackManager

console = Console()

# Exit codes for CI/CD systems
class ExitCodes:
    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIG_ERROR = 2
    VALIDATION_ERROR = 3
    AWS_ERROR = 4


def setup_logging(log_level: str, json_output: bool = False) -> logging.Logger:
    """Configure logging with optional JSON output for CI systems."""
    logger = logging.getLogger()
    logger.handlers.clear()
    
    if json_output:
        # Structured logging for CI/CD
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","message":"%(message)s"}'
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
    else:
        # Rich formatting for human-readable output
        handler = RichHandler(console=console, show_time=True, show_path=False)
    
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Suppress verbose library logs
    logging.getLogger("pulumi").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logger


def validate_aws_account_id(ctx, param, value: str) -> str:
    """Validate AWS account ID format."""
    if not value:
        raise click.BadParameter("AWS Account ID is required")
    
    if not (value.isdigit() and len(value) == 12):
        raise click.BadParameter(
            f"Invalid AWS Account ID format: {value}. Must be exactly 12 digits."
        )
    return value


def validate_roles_directory(ctx, param, value: str) -> Path:
    """Validate roles directory exists."""
    path = Path(value)
    if not path.exists():
        raise click.BadParameter(f"Roles directory does not exist: {value}")
    if not path.is_dir():
        raise click.BadParameter(f"Path is not a directory: {value}")
    return path


@click.group()
@click.version_option(version="1.0.0", prog_name="oidc-role-manager")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
    envvar="OIDC_LOG_LEVEL",
    help="Set logging level (env: OIDC_LOG_LEVEL)"
)
@click.option(
    "--json-output",
    is_flag=True,
    envvar="OIDC_JSON_OUTPUT",
    help="Output structured JSON logs for CI/CD (env: OIDC_JSON_OUTPUT)"
)
@click.pass_context
def cli(ctx, log_level: str, json_output: bool):
    """Enterprise OIDC Role Manager for AWS IAM and GitHub Actions."""
    ctx.ensure_object(dict)
    ctx.obj["logger"] = setup_logging(log_level, json_output)
    ctx.obj["json_output"] = json_output


@cli.command()
@click.option(
    "--account-id",
    required=True,
    callback=validate_aws_account_id,
    envvar="AWS_ACCOUNT_ID",
    help="Target AWS Account ID (env: AWS_ACCOUNT_ID)"
)
@click.option(
    "--role-name",
    envvar="OIDC_ROLE_NAME",
    help="Specific role name to process. If not provided, processes all roles (env: OIDC_ROLE_NAME)"
)
@click.option(
    "--roles-dir",
    default=lambda: os.path.join(os.path.dirname(__file__), "roles"),
    callback=validate_roles_directory,
    envvar="OIDC_ROLES_DIR",
    help="Directory containing role definitions (env: OIDC_ROLES_DIR)"
)
@click.option(
    "--aws-region",
    envvar="AWS_REGION",
    help="AWS region for resource creation (env: AWS_REGION)"
)
@click.option(
    "--aws-profile",
    envvar="AWS_PROFILE",
    help="AWS profile to use (env: AWS_PROFILE)"
)
@click.option(
    "--stack-name",
    default="dev",
    envvar="PULUMI_STACK_NAME",
    help="Base stack name (will be combined with account ID) (env: PULUMI_STACK_NAME)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without applying them"
)
@click.option(
    "--auto-approve",
    is_flag=True,
    envvar="OIDC_AUTO_APPROVE",
    help="Automatically approve deployment without confirmation (env: OIDC_AUTO_APPROVE)"
)
@click.pass_context
def deploy(ctx, account_id: str, role_name: Optional[str], roles_dir: Path, 
          aws_region: Optional[str], aws_profile: Optional[str], 
          stack_name: str, dry_run: bool, auto_approve: bool):
    """Deploy OIDC roles to a specified AWS account."""
    logger = ctx.obj["logger"]
    json_output = ctx.obj["json_output"]
    
    # Create account-specific stack name
    account_stack_name = f"{stack_name}-{account_id}"
    
    try:
        # Log deployment start
        deployment_info = {
            "account_id": account_id,
            "role_name": role_name,
            "roles_dir": str(roles_dir),
            "aws_region": aws_region,
            "aws_profile": aws_profile,
            "stack_name": account_stack_name,
            "dry_run": dry_run
        }
        
        if json_output:
            logger.info(f"Starting deployment: {json.dumps(deployment_info)}")
        else:
            console.print(f"🚀 Starting OIDC Role Manager deployment", style="bold green")
            console.print(f"📋 Account ID: {account_id}")
            console.print(f"📁 Roles Directory: {roles_dir}")
            console.print(f"📦 Stack: {account_stack_name}")
            if role_name:
                console.print(f"🎯 Target Role: {role_name}")
            if dry_run:
                console.print("🔍 Preview Mode: Showing changes without applying", style="yellow")

        # Discover and validate role configurations
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=json_output
        ) as progress:
            if not json_output:
                task = progress.add_task("Discovering role configurations...", total=None)
            
            try:
                role_configurations = config_loader.discover_role_configs(
                    base_roles_dir=str(roles_dir),
                    target_account_id=account_id,
                    target_role_name=role_name
                )
            except config_loader.ConfigError as e:
                logger.error(f"Configuration error: {e}")
                sys.exit(ExitCodes.CONFIG_ERROR)
            except Exception as e:
                logger.error(f"Unexpected error during configuration discovery: {e}")
                sys.exit(ExitCodes.GENERAL_ERROR)

        if not role_configurations:
            if json_output:
                result = {
                    "status": "success",
                    "message": "No role configurations found",
                    "account_id": account_id,
                    "roles_processed": 0
                }
                console.print(json.dumps(result))
            else:
                console.print(f"ℹ️  No role configurations found for account {account_id}", style="yellow")
            sys.exit(ExitCodes.SUCCESS)

        # Initialize Pulumi manager with account-specific stack
        pulumi_manager = PulumiStackManager(
            project_name="oidc-role-manager",
            stack_name=account_stack_name,
            aws_region=aws_region,
            aws_profile=aws_profile,
            json_output=json_output # Pass json_output to PulumiStackManager
        )

        # Process configurations
        if dry_run:
            # Preview mode
            if not json_output:
                console.print("🔍 Generating deployment preview...", style="bold blue")
            
            try:
                # Pass role_configurations to preview_deployment
                preview_result = pulumi_manager.preview_deployment(role_configurations) 
                
                if json_output:
                    # Attempt to create a serializable summary of the preview
                    changes_summary = {}
                    if hasattr(preview_result, 'change_summary') and isinstance(preview_result.change_summary, dict):
                        changes_summary = {
                            "create": preview_result.change_summary.get("create", 0),
                            "update": preview_result.change_summary.get("update", 0),
                            "delete": preview_result.change_summary.get("delete", 0),
                            "same": preview_result.change_summary.get("same", 0),
                            "total_changes": sum(c for c in preview_result.change_summary.values() if isinstance(c, (int, float)))
                        }
                    elif hasattr(preview_result, 'steps'): 
                        changes_summary = {"steps_count": len(preview_result.steps)}

                    result = {
                        "status": "success",
                        "deployment_mode": "preview",
                        "account_id": account_id,
                        "stack_name": account_stack_name,
                        "roles_found": len(role_configurations),
                        "changes_summary": changes_summary
                    }
                    console.print(json.dumps(result, indent=2))
                else:
                    console.print("\n📊 Preview Summary:", style="bold")
                    console.print(f"🏦 Account: {account_id}")
                    console.print(f"✅ Roles to process: {len(role_configurations)}")
                    for config_item in role_configurations:
                        console.print(f"  - {config_item.role_name}")
                    
                    console.print("\n✅ Dry run preview completed. No changes were applied.", style="green")
                    
                sys.exit(ExitCodes.SUCCESS)
                
            except Exception as e:
                logger.error(f"Preview failed: {e}")
                sys.exit(ExitCodes.GENERAL_ERROR)
        else:
            # Actual deployment
            if not auto_approve and not json_output:
                console.print("\n📋 About to deploy:", style="bold")
                console.print(f"🏦 Account: {account_id}")
                for config in role_configurations:
                    console.print(f"  - {config.role_name}")
                
                if not click.confirm("\nProceed with deployment?"):
                    console.print("Deployment cancelled by user", style="yellow")
                    sys.exit(ExitCodes.SUCCESS)
            
            try:
                if not json_output:
                    console.print("🚀 Deploying resources...", style="bold green")
                
                up_result = pulumi_manager.deploy(role_configurations)
                
                # Get outputs
                outputs = pulumi_manager.get_outputs()
                
                if json_output:
                    result = {
                        "status": "success",
                        "deployment_mode": "deploy",
                        "account_id": account_id,
                        "stack_name": account_stack_name,
                        "roles_deployed": len(role_configurations),
                        "outputs": {k: v.value for k, v in outputs.items()},
                        "summary": up_result.summary.message if up_result.summary else None
                    }
                    console.print(json.dumps(result, indent=2))
                else:
                    console.print("\n🎉 Deployment successful!", style="bold green")
                    console.print(f"🏦 Account: {account_id}")
                    console.print(f"✅ Deployed {len(role_configurations)} role(s)")
                    
                    if outputs:
                        console.print("\n📤 Stack Outputs:", style="bold")
                        table = Table()
                        table.add_column("Output", style="cyan")
                        table.add_column("Value", style="green")
                        
                        for key, output in outputs.items():
                            table.add_row(key, str(output.value))
                        
                        console.print(table)

                sys.exit(ExitCodes.SUCCESS)
                
            except Exception as e:
                logger.error(f"Deployment failed: {e}")
                sys.exit(ExitCodes.GENERAL_ERROR)
            
    except KeyboardInterrupt:
        logger.warning("Deployment interrupted by user")
        sys.exit(ExitCodes.GENERAL_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if ctx.obj.get("logger", logging.getLogger()).level == logging.DEBUG:
            import traceback
            traceback.print_exc()
        sys.exit(ExitCodes.GENERAL_ERROR)


@cli.command()
@click.option(
    "--account-id",
    required=True,
    callback=validate_aws_account_id,
    envvar="AWS_ACCOUNT_ID",
    help="Target AWS Account ID (env: AWS_ACCOUNT_ID)"
)
@click.option(
    "--stack-name",
    default="dev",
    envvar="PULUMI_STACK_NAME",
    help="Base stack name (will be combined with account ID) (env: PULUMI_STACK_NAME)"
)
@click.option(
    "--auto-approve",
    is_flag=True,
    envvar="OIDC_AUTO_APPROVE",
    help="Automatically approve destruction without confirmation (env: OIDC_AUTO_APPROVE)"
)
@click.pass_context
def destroy(ctx, account_id: str, stack_name: str, auto_approve: bool):
    """Destroy all deployed OIDC roles for a specific account."""
    logger = ctx.obj["logger"]
    json_output = ctx.obj["json_output"]
    
    # Create account-specific stack name
    account_stack_name = f"{stack_name}-{account_id}"
    
    try:
        pulumi_manager = PulumiStackManager(
            project_name="oidc-role-manager",
            stack_name=account_stack_name
        )
        
        # Check if stack exists
        stack_info = pulumi_manager.get_stack_info()
        if not stack_info:
            if json_output:
                console.print(json.dumps({
                    "status": "error", 
                    "message": "Stack not found",
                    "account_id": account_id,
                    "stack_name": account_stack_name
                }))
            else:
                console.print(f"❌ Stack '{account_stack_name}' not found", style="red")
                console.print(f"💡 No resources deployed for account {account_id}", style="blue")
            sys.exit(ExitCodes.CONFIG_ERROR)
        
        if not auto_approve and not json_output:
            console.print(f"⚠️  About to destroy stack: {account_stack_name}", style="bold red")
            console.print(f"🏦 Account: {account_id}")
            console.print("This will delete all OIDC roles managed by this stack!")
            
            if not click.confirm("Are you sure you want to proceed?"):
                console.print("Destruction cancelled by user", style="yellow")
                sys.exit(ExitCodes.SUCCESS)
        
        if not json_output:
            console.print("🗑️  Destroying resources...", style="bold red")
            console.print(f"🏦 Account: {account_id}")
        
        destroy_result = pulumi_manager.destroy()
        
        if json_output:
            result = {
                "status": "success",
                "message": "Stack destroyed successfully",
                "account_id": account_id,
                "stack_name": account_stack_name
            }
            console.print(json.dumps(result))
        else:
            console.print("✅ Stack destroyed successfully!", style="green")
            console.print(f"🏦 Account {account_id} resources removed")
        
        sys.exit(ExitCodes.SUCCESS)
        
    except Exception as e:
        logger.error(f"Destroy failed: {e}")
        sys.exit(ExitCodes.GENERAL_ERROR)


@cli.command()
@click.option(
    "--roles-dir",
    default=lambda: os.path.join(os.path.dirname(__file__), "roles"),
    callback=validate_roles_directory,
    help="Directory containing role definitions"
)
@click.pass_context
def validate(ctx, roles_dir: Path):
    """Validate role configurations without deploying."""
    logger = ctx.obj["logger"]
    
    try:
        # Get all account directories
        account_dirs = [d for d in roles_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        
        if not account_dirs:
            console.print("❌ No account directories found", style="red")
            sys.exit(ExitCodes.CONFIG_ERROR)
        
        total_errors = 0
        for account_dir in account_dirs:
            account_id = account_dir.name
            console.print(f"\n🔍 Validating account: {account_id}")
            
            try:
                configs = config_loader.discover_role_configs(
                    str(roles_dir), account_id
                )
                
                if configs:
                    console.print(f"✅ Found {len(configs)} valid role(s)")
                    for config in configs:
                        console.print(f"  - {config.role_name}")
                else:
                    console.print("⚠️  No roles found", style="yellow")
                    
            except config_loader.ConfigError as e:
                console.print(f"❌ Configuration error: {e}", style="red")
                total_errors += 1
        
        if total_errors > 0:
            console.print(f"\n❌ Validation completed with {total_errors} error(s)", style="red")
            sys.exit(ExitCodes.CONFIG_ERROR)
        else:
            console.print("\n✅ All configurations are valid!", style="green")
            sys.exit(ExitCodes.SUCCESS)
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(ExitCodes.GENERAL_ERROR)


@cli.command()
@click.option(
    "--account-id",
    required=True,
    callback=validate_aws_account_id,
    envvar="AWS_ACCOUNT_ID",
    help="Target AWS Account ID (env: AWS_ACCOUNT_ID)"
)
@click.option(
    "--stack-name",
    default="dev",
    envvar="PULUMI_STACK_NAME",
    help="Base stack name (will be combined with account ID) (env: PULUMI_STACK_NAME)"
)
@click.pass_context
def status(ctx, account_id: str, stack_name: str):
    """Show deployment status and outputs for a specific account."""
    logger = ctx.obj["logger"]
    json_output = ctx.obj["json_output"]
    
    # Create account-specific stack name
    account_stack_name = f"{stack_name}-{account_id}"
    
    try:
        pulumi_manager = PulumiStackManager(
            project_name="oidc-role-manager",
            stack_name=account_stack_name
        )
        
        stack_info = pulumi_manager.get_stack_info()
        if not stack_info:
            if json_output:
                console.print(json.dumps({
                    "status": "not_found", 
                    "account_id": account_id,
                    "stack_name": account_stack_name
                }))
            else:
                console.print(f"❌ Stack '{account_stack_name}' not found", style="red")
                console.print(f"💡 No resources deployed for account {account_id}", style="blue")
            sys.exit(ExitCodes.CONFIG_ERROR)
        
        outputs = pulumi_manager.get_outputs()
        
        if json_output:
            result = {
                "status": "found",
                "account_id": account_id,
                "stack_name": account_stack_name,
                "outputs": {k: v.value for k, v in outputs.items()},
                "update_time": getattr(stack_info, 'update_time', None)
            }
            console.print(json.dumps(result, indent=2))
        else:
            console.print(f"📦 Stack: {account_stack_name}", style="bold")
            console.print(f"🏦 Account: {account_id}")
            
            # Try to get update time info - different attributes might be available
            update_time = None
            for attr in ['update_time', 'last_update', 'last_modified']:
                if hasattr(stack_info, attr):
                    update_time = getattr(stack_info, attr)
                    break
            
            console.print(f"🕐 Last Update: {update_time or 'Unknown'}")
            
            if outputs:
                console.print("\n📤 Outputs:", style="bold")
                table = Table()
                table.add_column("Output", style="cyan")
                table.add_column("Value", style="green")
                
                for key, output in outputs.items():
                    table.add_row(key, str(output.value))
                
                console.print(table)
            else:
                console.print("No outputs available")
        
        sys.exit(ExitCodes.SUCCESS)
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        sys.exit(ExitCodes.GENERAL_ERROR)


@cli.command()
@click.option(
    "--stack-name",
    default="dev",
    envvar="PULUMI_STACK_NAME",
    help="Base stack name to search for (env: PULUMI_STACK_NAME)"
)
@click.pass_context
def list_stacks(ctx, stack_name: str):
    """List all deployed stacks across accounts."""
    logger = ctx.obj["logger"]
    json_output = ctx.obj["json_output"]
    
    try:
        import os
        import re
        from pathlib import Path
        
        # Look for stack files in the Pulumi state directory
        state_dir = Path.cwd() / '.pulumi-state' / '.pulumi' / 'stacks' / 'oidc-role-manager'
        
        if not state_dir.exists():
            if json_output:
                console.print(json.dumps({"status": "no_stacks", "stacks": []}))
            else:
                console.print("📭 No stacks found", style="yellow")
            sys.exit(ExitCodes.SUCCESS)
        
        # Find all stack files
        stack_files = list(state_dir.glob("*.json"))
        stack_pattern = re.compile(rf"{re.escape(stack_name)}-(\d{{12}})\.json$")
        
        found_stacks = []
        for stack_file in stack_files:
            match = stack_pattern.match(stack_file.name)
            if match:
                account_id = match.group(1)
                account_stack_name = f"{stack_name}-{account_id}"
                
                # Try to get stack info
                try:
                    pulumi_manager = PulumiStackManager(
                        project_name="oidc-role-manager",
                        stack_name=account_stack_name
                    )
                    
                    stack_info = pulumi_manager.get_stack_info()
                    outputs = pulumi_manager.get_outputs()
                    
                    stack_data = {
                        "account_id": account_id,
                        "stack_name": account_stack_name,
                        "has_resources": len(outputs) > 0,
                        "output_count": len(outputs)
                    }
                    
                    # Try to get update time
                    for attr in ['update_time', 'last_update', 'last_modified']:
                        if hasattr(stack_info, attr):
                            stack_data["last_update"] = getattr(stack_info, attr)
                            break
                    else:
                        stack_data["last_update"] = None
                    
                    found_stacks.append(stack_data)
                    
                except Exception as e:
                    logger.debug(f"Failed to get info for stack {account_stack_name}: {e}")
        
        if json_output:
            result = {
                "status": "success",
                "base_stack_name": stack_name,
                "total_stacks": len(found_stacks),
                "stacks": found_stacks
            }
            console.print(json.dumps(result, indent=2))
        else:
            if not found_stacks:
                console.print(f"📭 No stacks found with base name '{stack_name}'", style="yellow")
            else:
                console.print(f"📦 Found {len(found_stacks)} stack(s):", style="bold")
                
                table = Table()
                table.add_column("Account ID", style="cyan")
                table.add_column("Stack Name", style="blue")
                table.add_column("Resources", style="green")
                table.add_column("Last Update", style="yellow")
                
                for stack in found_stacks:
                    resources_status = "✅ Active" if stack["has_resources"] else "🚫 Empty"
                    last_update = stack.get("last_update", "Unknown")
                    if last_update and hasattr(last_update, 'strftime'):
                        last_update = last_update.strftime("%Y-%m-%d %H:%M")
                    
                    table.add_row(
                        stack["account_id"],
                        stack["stack_name"],
                        resources_status,
                        str(last_update)
                    )
                
                console.print(table)
        
        sys.exit(ExitCodes.SUCCESS)
        
    except Exception as e:
        logger.error(f"Failed to list stacks: {e}")
        sys.exit(ExitCodes.GENERAL_ERROR)


if __name__ == "__main__":
    cli() 