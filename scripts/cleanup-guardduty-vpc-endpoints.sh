#!/bin/bash

# GuardDuty VPC Endpoint Cleanup Script
# This script handles the VPC endpoint cleanup issue that blocks CDK destroy

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-}"

echo -e "${BLUE}=== GuardDuty VPC Endpoint Cleanup ===${NC}"

# Function to run AWS CLI with optional profile
aws_cmd() {
    if [ -n "$PROFILE" ]; then
        aws --profile "$PROFILE" --region "$REGION" "$@"
    else
        aws --region "$REGION" "$@"
    fi
}

# Function to find VPC endpoints blocking subnet deletion
find_blocking_vpc_endpoints() {
    echo -e "${YELLOW}Finding VPC endpoints that may block subnet deletion...${NC}"
    
    # Get all VPC endpoints in the region
    VPC_ENDPOINTS=$(aws_cmd ec2 describe-vpc-endpoints \
        --query 'VpcEndpoints[].{Id:VpcEndpointId,Service:ServiceName,State:State,VpcId:VpcId}' \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$VPC_ENDPOINTS" != "[]" ]; then
        echo "Found VPC endpoints:"
        echo "$VPC_ENDPOINTS" | jq -r '.[] | "  \(.Id) - \(.Service) (\(.State)) in VPC \(.VpcId)"'
        
        # Look for GuardDuty-related endpoints
        GUARDDUTY_ENDPOINTS=$(echo "$VPC_ENDPOINTS" | jq -r '.[] | select(.Service | contains("guardduty")) | .Id')
        
        if [ -n "$GUARDDUTY_ENDPOINTS" ]; then
            echo -e "${RED}GuardDuty VPC endpoints found:${NC}"
            echo "$GUARDDUTY_ENDPOINTS"
            return 0
        else
            echo -e "${GREEN}No GuardDuty VPC endpoints found${NC}"
            return 1
        fi
    else
        echo -e "${GREEN}No VPC endpoints found${NC}"
        return 1
    fi
}

# Function to find network interfaces blocking subnet deletion
find_blocking_network_interfaces() {
    echo -e "${YELLOW}Finding network interfaces that may block subnet deletion...${NC}"
    
    # Get network interfaces that are available but not attached
    AVAILABLE_ENIS=$(aws_cmd ec2 describe-network-interfaces \
        --filters "Name=status,Values=available" \
        --query 'NetworkInterfaces[?!Attachment].{Id:NetworkInterfaceId,SubnetId:SubnetId,Description:Description}' \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$AVAILABLE_ENIS" != "[]" ]; then
        echo "Found available network interfaces:"
        echo "$AVAILABLE_ENIS" | jq -r '.[] | "  \(.Id) in subnet \(.SubnetId) - \(.Description)"'
        
        # Try to delete them (some may be managed by AWS services and can't be deleted)
        echo "$AVAILABLE_ENIS" | jq -r '.[].Id' | while read -r eni; do
            if [ -n "$eni" ]; then
                echo "Attempting to delete ENI: $eni"
                if aws_cmd ec2 delete-network-interface --network-interface-id "$eni" 2>/dev/null; then
                    echo -e "${GREEN}  Successfully deleted $eni${NC}"
                else
                    echo -e "${YELLOW}  Could not delete $eni (may be managed by AWS service)${NC}"
                fi
            fi
        done
    else
        echo -e "${GREEN}No available network interfaces found${NC}"
    fi
}

# Function to perform ordered CDK destroy
perform_ordered_destroy() {
    echo -e "${YELLOW}Performing ordered CDK stack destruction...${NC}"
    
    cd /Users/atewari/Documents/Code/multi-agent-sample-deployment/infra
    
    # Get list of stacks
    STACKS=$(npx cdk list 2>/dev/null || echo "")
    
    if [ -z "$STACKS" ]; then
        echo -e "${RED}No CDK stacks found${NC}"
        return 1
    fi
    
    echo "Found stacks: $STACKS"
    
    # Destroy in reverse dependency order
    for stack_pattern in "ecs" "database" "vpc" "network"; do
        MATCHING_STACK=$(echo "$STACKS" | grep -i "$stack_pattern" | head -1)
        if [ -n "$MATCHING_STACK" ]; then
            echo -e "${BLUE}Destroying stack: $MATCHING_STACK${NC}"
            
            # First attempt
            if npx cdk destroy "$MATCHING_STACK" --force; then
                echo -e "${GREEN}Successfully destroyed $MATCHING_STACK${NC}"
            else
                echo -e "${YELLOW}First attempt failed, cleaning up network interfaces and retrying...${NC}"
                
                # Clean up network interfaces and retry
                find_blocking_network_interfaces
                sleep 30
                
                echo "Retrying destruction of $MATCHING_STACK..."
                if npx cdk destroy "$MATCHING_STACK" --force; then
                    echo -e "${GREEN}Successfully destroyed $MATCHING_STACK on retry${NC}"
                else
                    echo -e "${RED}Failed to destroy $MATCHING_STACK even after cleanup${NC}"
                fi
            fi
            
            # Wait between stack destructions
            sleep 10
        fi
    done
}

# Main execution
main() {
    echo "Starting GuardDuty VPC endpoint cleanup process..."
    echo ""
    
    # Step 1: Identify blocking resources
    find_blocking_vpc_endpoints
    echo ""
    
    find_blocking_network_interfaces
    echo ""
    
    # Step 2: Perform ordered destroy
    perform_ordered_destroy
    echo ""
    
    # Step 3: Final verification
    echo -e "${YELLOW}Verifying cleanup...${NC}"
    REMAINING_STACKS=$(aws_cmd cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --query 'StackSummaries[?contains(StackName, `MultiAgent`) || contains(StackName, `multi-agent`)].StackName' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_STACKS" ] && [ "$REMAINING_STACKS" != "None" ]; then
        echo -e "${RED}Remaining stacks: $REMAINING_STACKS${NC}"
    else
        echo -e "${GREEN}All stacks successfully cleaned up${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}=== Cleanup completed ===${NC}"
    echo -e "${YELLOW}Note: GuardDuty VPC endpoints are managed by AWS and will be recreated when ECS Fargate is deployed again.${NC}"
}

# Check for help
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "GuardDuty VPC Endpoint Cleanup Script"
    echo ""
    echo "Usage: $0"
    echo ""
    echo "Environment variables:"
    echo "  AWS_PROFILE       - AWS profile to use"
    echo "  AWS_DEFAULT_REGION - AWS region (default: us-east-1)"
    echo ""
    echo "This script handles VPC endpoint cleanup that blocks CDK destroy operations."
    exit 0
fi

# Run main function
main
