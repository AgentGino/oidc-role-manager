#!/bin/bash
#
# Cross-Account OIDC Role Deployment Script
# Demonstrates different authentication patterns for enterprise deployments
#

set -euo pipefail

# Configuration
ACCOUNTS=(
    "123456789012:account-a-profile:account-a-role"
    "987654321098:account-b-profile:account-b-role"  
    "555666777888:account-c-profile:account-c-role"
)
BASE_ROLE_ARN_TEMPLATE="arn:aws:iam::%s:role/CrossAccountDeploymentRole"
EXTERNAL_ID="${AWS_EXTERNAL_ID:-}"
DRY_RUN="${DRY_RUN:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to deploy using profile-based authentication
deploy_with_profile() {
    local account_id="$1"
    local profile="$2"
    
    log "Deploying to account $account_id using profile $profile"
    
    local cmd="python cli.py deploy --account-id $account_id --aws-profile $profile --json-output"
    if [[ "$DRY_RUN" == "true" ]]; then
        cmd="$cmd --dry-run"
    fi
    
    if eval "$cmd"; then
        success "Deployment to $account_id completed"
    else
        error "Deployment to $account_id failed"
        return 1
    fi
}

# Function to deploy using cross-account role assumption
deploy_with_role_assumption() {
    local account_id="$1"
    local base_profile="$2"
    
    local assume_role_arn
    assume_role_arn=$(printf "$BASE_ROLE_ARN_TEMPLATE" "$account_id")
    
    log "Deploying to account $account_id using role assumption"
    log "Base profile: $base_profile"
    log "Assume role: $assume_role_arn"
    
    local cmd="python cli.py deploy --account-id $account_id --aws-profile $base_profile --assume-role-arn $assume_role_arn --json-output"
    
    if [[ -n "$EXTERNAL_ID" ]]; then
        cmd="$cmd --external-id $EXTERNAL_ID"
        log "Using external ID for additional security"
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        cmd="$cmd --dry-run"
    fi
    
    if eval "$cmd"; then
        success "Cross-account deployment to $account_id completed"
    else
        error "Cross-account deployment to $account_id failed"
        return 1
    fi
}

# Function to deploy using environment variables
deploy_with_env_vars() {
    local account_id="$1"
    local assume_role_arn="$2"
    
    log "Deploying to account $account_id using environment variables"
    
    export AWS_ACCOUNT_ID="$account_id"
    export AWS_ASSUME_ROLE_ARN="$assume_role_arn"
    if [[ -n "$EXTERNAL_ID" ]]; then
        export AWS_EXTERNAL_ID="$EXTERNAL_ID"
    fi
    
    local cmd="python cli.py deploy --json-output"
    if [[ "$DRY_RUN" == "true" ]]; then
        cmd="$cmd --dry-run"
    fi
    
    if eval "$cmd"; then
        success "Environment-based deployment to $account_id completed"
    else
        error "Environment-based deployment to $account_id failed"
        return 1
    fi
}

# Function to validate prerequisites
validate_prerequisites() {
    log "Validating prerequisites..."
    
    # Check if cli.py exists
    if [[ ! -f "cli.py" ]]; then
        error "cli.py not found. Run this script from the oidc-role-manager directory."
        exit 1
    fi
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error "AWS CLI not found. Please install it first."
        exit 1
    fi
    
    # Check Python
    if ! command -v python &> /dev/null; then
        error "Python not found. Please install it first."
        exit 1
    fi
    
    success "Prerequisites validated"
}

# Main deployment function
deploy_all_accounts() {
    local deployment_method="${1:-profile}"
    
    log "Starting cross-account deployment using method: $deployment_method"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        warn "DRY RUN MODE - No actual changes will be made"
    fi
    
    local failed_accounts=()
    
    for account_config in "${ACCOUNTS[@]}"; do
        IFS=':' read -r account_id profile role_suffix <<< "$account_config"
        
        case "$deployment_method" in
            "profile")
                if ! deploy_with_profile "$account_id" "$profile"; then
                    failed_accounts+=("$account_id")
                fi
                ;;
            "assume-role")
                if ! deploy_with_role_assumption "$account_id" "$profile"; then
                    failed_accounts+=("$account_id")
                fi
                ;;
            "env-vars")
                local assume_role_arn
                assume_role_arn=$(printf "$BASE_ROLE_ARN_TEMPLATE" "$account_id")
                if ! deploy_with_env_vars "$account_id" "$assume_role_arn"; then
                    failed_accounts+=("$account_id")
                fi
                ;;
            *)
                error "Unknown deployment method: $deployment_method"
                exit 1
                ;;
        esac
        
        # Brief pause between deployments
        sleep 2
    done
    
    # Summary
    echo
    log "Deployment Summary:"
    local total_accounts=${#ACCOUNTS[@]}
    local failed_count=${#failed_accounts[@]}
    local success_count=$((total_accounts - failed_count))
    
    success "Successful deployments: $success_count/$total_accounts"
    
    if [[ $failed_count -gt 0 ]]; then
        error "Failed deployments: $failed_count/$total_accounts"
        error "Failed accounts: ${failed_accounts[*]}"
        exit 1
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Cross-Account OIDC Role Deployment Script

Usage: $0 [OPTIONS] [METHOD]

Methods:
  profile      - Use AWS profiles (default)
  assume-role  - Use cross-account role assumption  
  env-vars     - Use environment variables

Options:
  -h, --help   - Show this help message
  -d, --dry-run - Preview changes without applying
  
Environment Variables:
  AWS_EXTERNAL_ID - External ID for role assumption
  DRY_RUN         - Set to 'true' for dry run mode

Examples:
  # Deploy using AWS profiles
  $0 profile
  
  # Preview deployment using role assumption
  DRY_RUN=true $0 assume-role
  
  # Deploy using environment variables with external ID
  AWS_EXTERNAL_ID="my-unique-id" $0 env-vars

EOF
}

# Parse command line arguments
main() {
    local method="profile"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -d|--dry-run)
                DRY_RUN="true"
                shift
                ;;
            profile|assume-role|env-vars)
                method="$1"
                shift
                ;;
            *)
                error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    validate_prerequisites
    deploy_all_accounts "$method"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 