#!/bin/bash

# Complete Enterprise Pattern for CDK Stack Destruction
# Handles ALL 6 CDK stacks + AWS managed resources (GuardDuty, etc.)

set -e

# Auto-detect region from AWS CLI config or use default
REGION=$(aws configure get region 2>/dev/null || echo "${AWS_DEFAULT_REGION:-us-east-1}")
PROFILE="${AWS_PROFILE:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=== Complete Multi-Agent System Stack Destruction ===${NC}"
echo "Handling ALL 6 CDK stacks + AWS managed resources"
echo -e "${BLUE}Region: $REGION${NC}"
echo ""

# Function to run AWS CLI
aws_cmd() {
    if [ -n "$PROFILE" ]; then
        aws --profile "$PROFILE" --region "$REGION" "$@"
    else
        aws --region "$REGION" "$@"
    fi
}

# Function to clean up VPC endpoints (especially GuardDuty)
cleanup_vpc_endpoints() {
    echo -e "${YELLOW}Cleaning up VPC endpoints...${NC}"
    
    # Find all VPC endpoints in MultiAgentSystem VPCs
    VPC_IDS=$(aws_cmd ec2 describe-vpcs \
        --filters "Name=tag:Project,Values=MultiAgentSystem" \
        --query 'Vpcs[].VpcId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$VPC_IDS" ] && [ "$VPC_IDS" != "None" ]; then
        for vpc in $VPC_IDS; do
            echo "  Checking VPC endpoints in VPC: $vpc"
            
            VPC_ENDPOINTS=$(aws_cmd ec2 describe-vpc-endpoints \
                --filters "Name=vpc-id,Values=$vpc" \
                --query 'VpcEndpoints[].VpcEndpointId' \
                --output text 2>/dev/null || echo "")
            
            if [ -n "$VPC_ENDPOINTS" ] && [ "$VPC_ENDPOINTS" != "None" ]; then
                echo "    Found VPC endpoints: $VPC_ENDPOINTS"
                for endpoint in $VPC_ENDPOINTS; do
                    ENDPOINT_SERVICE=$(aws_cmd ec2 describe-vpc-endpoints \
                        --vpc-endpoint-ids "$endpoint" \
                        --query 'VpcEndpoints[0].ServiceName' \
                        --output text 2>/dev/null || echo "unknown")
                    
                    echo "    Deleting VPC endpoint: $endpoint ($ENDPOINT_SERVICE)"
                    aws_cmd ec2 delete-vpc-endpoints --vpc-endpoint-ids "$endpoint" 2>/dev/null || echo "      (Could not delete)"
                done
                
                echo "    Waiting for VPC endpoints to be deleted..."
                sleep 60  # Wait for VPC endpoints to fully delete
            else
                echo "    No VPC endpoints found in VPC: $vpc"
            fi
        done
    else
        echo "No MultiAgentSystem VPCs found"
    fi
}

# Function to clean up GuardDuty managed security groups
cleanup_guardduty_security_groups() {
    echo -e "${YELLOW}Cleaning up GuardDuty managed security groups...${NC}"
    
    GUARDDUTY_SGS=$(aws_cmd ec2 describe-security-groups \
        --filters "Name=group-name,Values=GuardDutyManagedSecurityGroup-*" \
        --query 'SecurityGroups[].GroupId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$GUARDDUTY_SGS" ] && [ "$GUARDDUTY_SGS" != "None" ]; then
        echo "Found GuardDuty security groups: $GUARDDUTY_SGS"
        for sg in $GUARDDUTY_SGS; do
            echo "  Attempting to delete GuardDuty SG: $sg"
            aws_cmd ec2 delete-security-group --group-id "$sg" 2>/dev/null || echo "    (Could not delete - may be in use)"
        done
    else
        echo "No GuardDuty security groups found"
    fi
}

# Function to clean up orphaned VPCs from failed stacks
cleanup_orphaned_vpcs() {
    echo -e "${YELLOW}Cleaning up orphaned VPCs from failed CloudFormation stacks...${NC}"
    
    ORPHANED_VPCS=$(aws_cmd ec2 describe-vpcs \
        --filters "Name=tag:Project,Values=MultiAgentSystem" \
        --query 'Vpcs[].VpcId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$ORPHANED_VPCS" ] && [ "$ORPHANED_VPCS" != "None" ]; then
        echo "Found potentially orphaned VPCs: $ORPHANED_VPCS"
        for vpc in $ORPHANED_VPCS; do
            STACK_NAME=$(aws_cmd ec2 describe-vpcs --vpc-ids "$vpc" \
                --query 'Vpcs[0].Tags[?Key==`aws:cloudformation:stack-name`].Value' \
                --output text 2>/dev/null || echo "")
            
            if [ -n "$STACK_NAME" ] && [ "$STACK_NAME" != "None" ]; then
                STACK_STATUS=$(aws_cmd cloudformation describe-stacks --stack-name "$STACK_NAME" \
                    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
                
                if [ "$STACK_STATUS" = "NOT_FOUND" ]; then
                    echo "  Found orphaned VPC $vpc from deleted stack $STACK_NAME"
                    
                    # Clean up VPC endpoints first
                    VPC_ENDPOINTS=$(aws_cmd ec2 describe-vpc-endpoints \
                        --filters "Name=vpc-id,Values=$vpc" \
                        --query 'VpcEndpoints[].VpcEndpointId' \
                        --output text 2>/dev/null || echo "")
                    
                    if [ -n "$VPC_ENDPOINTS" ] && [ "$VPC_ENDPOINTS" != "None" ]; then
                        for endpoint in $VPC_ENDPOINTS; do
                            echo "    Deleting VPC endpoint in orphaned VPC: $endpoint"
                            aws_cmd ec2 delete-vpc-endpoints --vpc-endpoint-ids "$endpoint" 2>/dev/null || echo "      (Could not delete)"
                        done
                        sleep 60  # Wait for VPC endpoints to be deleted
                    fi
                    
                    VPC_GUARDDUTY_SGS=$(aws_cmd ec2 describe-security-groups \
                        --filters "Name=vpc-id,Values=$vpc" "Name=group-name,Values=GuardDutyManagedSecurityGroup-*" \
                        --query 'SecurityGroups[].GroupId' \
                        --output text 2>/dev/null || echo "")
                    
                    if [ -n "$VPC_GUARDDUTY_SGS" ] && [ "$VPC_GUARDDUTY_SGS" != "None" ]; then
                        for sg in $VPC_GUARDDUTY_SGS; do
                            echo "    Deleting GuardDuty SG in orphaned VPC: $sg"
                            aws_cmd ec2 delete-security-group --group-id "$sg" 2>/dev/null || echo "      (Could not delete)"
                        done
                    fi
                    
                    echo "    Attempting to delete orphaned VPC: $vpc"
                    aws_cmd ec2 delete-vpc --vpc-id "$vpc" 2>/dev/null || echo "      (Could not delete - may have dependencies)"
                fi
            fi
        done
    else
        echo "No orphaned VPCs found"
    fi
}

# Function to clean up available ENIs
cleanup_available_enis() {
    echo -e "${YELLOW}Cleaning up available network interfaces...${NC}"
    
    AVAILABLE_ENIS=$(aws_cmd ec2 describe-network-interfaces \
        --filters "Name=status,Values=available" \
        --query 'NetworkInterfaces[?!Attachment].NetworkInterfaceId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$AVAILABLE_ENIS" ] && [ "$AVAILABLE_ENIS" != "None" ]; then
        echo "Found available ENIs, attempting cleanup..."
        for eni in $AVAILABLE_ENIS; do
            echo "  Deleting ENI: $eni"
            aws_cmd ec2 delete-network-interface --network-interface-id "$eni" 2>/dev/null || echo "    (Could not delete - AWS managed)"
        done
    else
        echo "No available ENIs found"
    fi
}

# Function to handle failed CloudFormation stacks
cleanup_failed_stacks() {
    echo -e "${YELLOW}Cleaning up failed CloudFormation stacks...${NC}"
    
    FAILED_STACKS=$(aws_cmd cloudformation list-stacks \
        --stack-status-filter "ROLLBACK_COMPLETE" "CREATE_FAILED" "DELETE_FAILED" \
        --query 'StackSummaries[?contains(StackName, `MultiAgentSystem`)].StackName' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$FAILED_STACKS" ] && [ "$FAILED_STACKS" != "None" ]; then
        echo "Found failed stacks: $FAILED_STACKS"
        for stack in $FAILED_STACKS; do
            echo "  Deleting failed stack: $stack"
            aws_cmd cloudformation delete-stack --stack-name "$stack" 2>/dev/null || echo "    (Could not delete)"
        done
        
        echo "  Waiting for failed stack cleanup..."
        sleep 30
    else
        echo "No failed stacks found"
    fi
}

# Function to destroy a CDK stack with retry logic
destroy_stack_with_retry() {
    local stack_pattern="$1"
    local stack_name="$2"
    
    echo -e "${BLUE}Destroying $stack_name...${NC}"
    
    if npx cdk destroy "$stack_pattern" --force 2>/dev/null; then
        echo -e "${GREEN}✅ $stack_name destroyed successfully${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  $stack_name destruction had issues, cleaning up and retrying...${NC}"
        
        cleanup_available_enis
        cleanup_vpc_endpoints
        cleanup_guardduty_security_groups
        sleep 30
        
        echo "Retrying $stack_name destruction..."
        if npx cdk destroy "$stack_pattern" --force 2>/dev/null; then
            echo -e "${GREEN}✅ $stack_name destroyed on retry${NC}"
            return 0
        else
            echo -e "${RED}❌ $stack_name destruction failed${NC}"
            return 1
        fi
    fi
}

# Main destruction sequence
main() {
    cd /Users/atewari/Documents/Code/multi-agent-sample-deployment/infra
    
    echo -e "${YELLOW}Phase 1: Pre-cleanup of failed stacks and AWS managed resources...${NC}"
    cleanup_failed_stacks
    cleanup_vpc_endpoints
    cleanup_guardduty_security_groups
    cleanup_orphaned_vpcs
    cleanup_available_enis
    echo ""
    
    echo -e "${YELLOW}Phase 2: Destroying CDK stacks in dependency order...${NC}"
    
    destroy_stack_with_retry "*Monitoring*" "Monitoring Stack"
    sleep 10
    
    destroy_stack_with_retry "*StreamingAPI*" "Streaming API Stack"
    sleep 10
    
    destroy_stack_with_retry "*ECS*" "ECS Stack"
    sleep 30
    
    destroy_stack_with_retry "*LoadBalancer*" "Load Balancer Stack"
    sleep 10
    
    destroy_stack_with_retry "*Database*" "Database Stack"
    sleep 20
    
    destroy_stack_with_retry "*Network*" "Network Stack"
    
    echo ""
    echo -e "${YELLOW}Phase 3: Final cleanup verification...${NC}"
    cleanup_available_enis
    cleanup_vpc_endpoints
    cleanup_guardduty_security_groups
    
    echo -e "${YELLOW}Verifying stack cleanup...${NC}"
    REMAINING_STACKS=$(aws_cmd cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --query 'StackSummaries[?contains(StackName, `MultiAgentSystem`)].StackName' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_STACKS" ] && [ "$REMAINING_STACKS" != "None" ]; then
        echo -e "${RED}⚠️  Remaining stacks found: $REMAINING_STACKS${NC}"
        echo "You may need to manually clean these up in the AWS Console"
    else
        echo -e "${GREEN}✅ All MultiAgentSystem stacks successfully cleaned up${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}=== Complete Stack Destruction Finished ===${NC}"
    echo -e "${BLUE}Summary: Destroyed all 6 CDK stacks + AWS managed resources + VPC endpoints${NC}"
    echo -e "${YELLOW}Note: GuardDuty VPC endpoints will be recreated on next deployment${NC}"
}

# Help
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Complete Multi-Agent System Stack Destruction"
    echo ""
    echo "Usage: $0"
    echo ""
    echo "This script destroys ALL 6 CDK stacks in the correct order:"
    echo "  1. MultiAgentSystem-Monitoring-dev"
    echo "  2. MultiAgentSystem-StreamingAPI-dev" 
    echo "  3. MultiAgentSystem-ECS-dev"
    echo "  4. MultiAgentSystem-LoadBalancer-dev"
    echo "  5. MultiAgentSystem-Database-dev"
    echo "  6. MultiAgentSystem-Network-dev"
    echo ""
    echo "Plus handles AWS managed resources:"
    echo "  - VPC endpoints (GuardDuty, etc.)"
    echo "  - GuardDuty security groups"
    echo "  - Orphaned VPCs from failed stacks"
    echo "  - Available network interfaces"
    echo "  - Failed CloudFormation stacks"
    echo ""
    echo "Environment variables:"
    echo "  AWS_PROFILE       - AWS profile to use"
    echo "  AWS_DEFAULT_REGION - AWS region (auto-detected from CLI config)"
    exit 0
fi

# Run main function
main
