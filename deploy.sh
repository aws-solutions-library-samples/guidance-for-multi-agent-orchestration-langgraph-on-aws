#!/bin/bash

# Multi-Agent Sample Deployment Script
# This script deploys the CDK infrastructure and updates frontend configuration
# Updated to support streaming functionality and proper region handling

set -e

echo "🚀 Starting Multi-Agent Sample Deployment..."

# Configuration
CDK_DIR="./infra"
FRONTEND_DIR="./frontend"
CDK_OUTPUTS_FILE="./cdk-outputs.json"
FRONTEND_ENV_FILE="$FRONTEND_DIR/.env"

# Get AWS region (prioritize environment variable, then AWS config, then default)
AWS_REGION="${CDK_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || echo 'us-east-1')}"
export CDK_DEFAULT_REGION="$AWS_REGION"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "ℹ️  $1"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Clean build artifacts and temporary files
clean_build_artifacts() {
    print_info "Cleaning build artifacts and temporary files..."
    
    # Clean CDK build artifacts
    if [ -d "$CDK_DIR" ]; then
        cd "$CDK_DIR"
        
        # Remove CDK build cache with proper cleanup
        if [ -d "cdk.out" ]; then
            print_info "Removing cdk.out directory..."
            chmod -R u+w cdk.out 2>/dev/null || true
            rm -rf cdk.out 2>/dev/null || {
                print_warning "Standard removal failed, using force cleanup..."
                find cdk.out -type f -delete 2>/dev/null || true
                find cdk.out -type d -empty -delete 2>/dev/null || true
                rmdir cdk.out 2>/dev/null || rm -rf cdk.out 2>/dev/null || true
            }
        fi
        
        # Remove CDK staging directory
        if [ -d ".cdk.staging" ]; then
            chmod -R u+w .cdk.staging 2>/dev/null || true
            rm -rf .cdk.staging 2>/dev/null || true
        fi
        
        # Clean Lambda function build artifacts
        find . -name "*.js" -path "*/resolver-function/*" -not -path "*/node_modules/*" -delete
        find . -name "*.js.map" -path "*/resolver-function/*" -not -path "*/node_modules/*" -delete
        find . -name "*.d.ts" -path "*/resolver-function/*" -not -path "*/node_modules/*" -delete
        
        # Clean stream processor build artifacts
        find . -name "*.js" -path "*/stream-processor-function/*" -not -path "*/node_modules/*" -delete
        find . -name "*.js.map" -path "*/stream-processor-function/*" -not -path "*/node_modules/*" -delete
        find . -name "*.d.ts" -path "*/stream-processor-function/*" -not -path "*/node_modules/*" -delete
        
        cd ..
    fi
    
    # Clean frontend build artifacts
    if [ -d "$FRONTEND_DIR" ]; then
        cd "$FRONTEND_DIR"
        rm -rf dist
        rm -rf .vite
        cd ..
    fi
    
    # Clean root level artifacts
    rm -f "$CDK_OUTPUTS_FILE"
    
    print_success "Build artifacts cleaned"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    command -v aws >/dev/null 2>&1 || { print_error "AWS CLI is required but not installed"; exit 1; }
    command -v cdk >/dev/null 2>&1 || { print_error "AWS CDK is required but not installed"; exit 1; }
    command -v node >/dev/null 2>&1 || { print_error "Node.js is required but not installed"; exit 1; }
    command -v jq >/dev/null 2>&1 || { print_error "jq is required but not installed"; exit 1; }
    
    print_success "Prerequisites check passed"
}

# Deploy CDK infrastructure
deploy_infrastructure() {
    print_info "Deploying CDK infrastructure to region: $AWS_REGION..."
    
    cd "$CDK_DIR"
    
    # Install dependencies
    if [ ! -d "node_modules" ]; then
        print_info "Installing CDK dependencies..."
        npm install
    fi
    
    # Compile TypeScript Lambda functions
    print_info "Compiling TypeScript Lambda functions..."
    
    # Compile resolver function
    if [ -f "lib/streaming-api/resolver-function/tsconfig.json" ]; then
        cd lib/streaming-api/resolver-function
        print_info "Compiling resolver function TypeScript..."
        npx tsc
        cd ../../..
    fi
    
    # Compile stream processor function
    if [ -f "lib/streaming-api/stream-processor-function/tsconfig.json" ]; then
        cd lib/streaming-api/stream-processor-function
        print_info "Compiling stream processor function TypeScript..."
        npx tsc
        cd ../../..
    fi
    
    # Verify TypeScript compilation succeeded
    print_info "Verifying TypeScript compilation..."
    
    # Check resolver function compilation
    if [ -f "lib/streaming-api/resolver-function/index.ts" ] && [ ! -f "lib/streaming-api/resolver-function/index.js" ]; then
        print_error "Resolver function TypeScript compilation failed - index.js not found"
        exit 1
    fi
    
    # Check stream processor compilation
    if [ -f "lib/streaming-api/stream-processor-function/index.ts" ] && [ ! -f "lib/streaming-api/stream-processor-function/index.js" ]; then
        print_error "Stream processor function TypeScript compilation failed - index.js not found"
        exit 1
    fi
    
    print_success "TypeScript compilation verified"
    
    # Bootstrap CDK (safe to run multiple times)
    print_info "Bootstrapping CDK in region $AWS_REGION..."
    cdk bootstrap --region "$AWS_REGION"
    
    # Deploy all stacks
    print_info "Deploying all CDK stacks..."
    cdk deploy --all --require-approval never --outputs-file "../cdk-outputs.json" --region "$AWS_REGION"
    
    cd ..
    print_success "CDK infrastructure deployed to $AWS_REGION"
}

# Validate streaming components deployment
validate_streaming_components() {
    print_info "Validating streaming components deployment..."
    
    if [ ! -f "$CDK_OUTPUTS_FILE" ]; then
        print_error "CDK outputs file not found: $CDK_OUTPUTS_FILE"
        exit 1
    fi
    
    # Find stack with streaming components
    STACK_NAME=$(jq -r 'to_entries[] | select(.value.GraphQLApiUrl) | .key' "$CDK_OUTPUTS_FILE" 2>/dev/null || echo "")
    
    if [ -z "$STACK_NAME" ]; then
        print_error "Could not find stack with GraphQL API in CDK outputs"
        exit 1
    fi
    
    # Check for required streaming outputs
    GRAPHQL_API_URL=$(jq -r ".[\"$STACK_NAME\"].GraphQLApiUrl // empty" "$CDK_OUTPUTS_FILE")
    GRAPHQL_API_ID=$(jq -r ".[\"$STACK_NAME\"].GraphQLApiId // empty" "$CDK_OUTPUTS_FILE")
    CHAT_MESSAGES_TABLE=$(jq -r ".[\"$STACK_NAME\"].ChatMessagesTableName // empty" "$CDK_OUTPUTS_FILE")
    
    # Validate streaming components
    [ -z "$GRAPHQL_API_URL" ] && { print_error "GraphQL API URL not found - streaming backend not deployed"; exit 1; }
    [ -z "$GRAPHQL_API_ID" ] && { print_error "GraphQL API ID not found - streaming backend not deployed"; exit 1; }
    [ -z "$CHAT_MESSAGES_TABLE" ] && { print_error "Chat Messages Table not found - streaming backend not deployed"; exit 1; }
    
    print_success "Streaming components validation passed"
    print_info "  • GraphQL API: $GRAPHQL_API_URL"
    print_info "  • GraphQL API ID: $GRAPHQL_API_ID"
    print_info "  • Chat Messages Table: $CHAT_MESSAGES_TABLE"
}

# Update frontend configuration
update_frontend_config() {
    print_info "Updating frontend configuration..."
    
    if [ ! -f "$CDK_OUTPUTS_FILE" ]; then
        print_error "CDK outputs file not found: $CDK_OUTPUTS_FILE"
        exit 1
    fi
    
    # Find stack with UserPoolId
    STACK_NAME=$(jq -r 'to_entries[] | select(.value.UserPoolId) | .key' "$CDK_OUTPUTS_FILE" 2>/dev/null || echo "")
    
    if [ -z "$STACK_NAME" ]; then
        print_error "Could not find stack with UserPoolId in CDK outputs"
        exit 1
    fi
    
    # Extract values
    USER_POOL_ID=$(jq -r ".[\"$STACK_NAME\"].UserPoolId // empty" "$CDK_OUTPUTS_FILE")
    USER_POOL_CLIENT_ID=$(jq -r ".[\"$STACK_NAME\"].UserPoolClientId // empty" "$CDK_OUTPUTS_FILE")
    GRAPHQL_API_URL=$(jq -r ".[\"$STACK_NAME\"].GraphQLApiUrl // empty" "$CDK_OUTPUTS_FILE")
    
    # Validate required values
    [ -z "$USER_POOL_ID" ] && { print_error "UserPoolId not found in CDK outputs"; exit 1; }
    [ -z "$USER_POOL_CLIENT_ID" ] && { print_error "UserPoolClientId not found in CDK outputs"; exit 1; }
    [ -z "$GRAPHQL_API_URL" ] && { print_error "GraphQLApiUrl not found in CDK outputs"; exit 1; }
    
    # Use the existing frontend setup script if available, otherwise create .env file
    if [ -f "$FRONTEND_DIR/scripts/setup-config.js" ]; then
        print_info "Using frontend setup-config script..."
        cd "$FRONTEND_DIR"
        npm run setup-config:cdk
        cd ..
        
        # Ensure AWS region is set correctly in .env
        if [ -f "$FRONTEND_ENV_FILE" ]; then
            # Update or add AWS region
            if grep -q "VITE_AWS_REGION" "$FRONTEND_ENV_FILE"; then
                sed -i.bak "s/VITE_AWS_REGION=.*/VITE_AWS_REGION=$AWS_REGION/" "$FRONTEND_ENV_FILE"
            else
                echo "VITE_AWS_REGION=$AWS_REGION" >> "$FRONTEND_ENV_FILE"
            fi
            rm -f "$FRONTEND_ENV_FILE.bak"
        fi
    else
        # Fallback: Create .env file from .env.example template
        print_warning "Frontend setup script not found, creating .env file from template..."
        
        if [ -f "$FRONTEND_DIR/.env.example" ]; then
            # Use .env.example as template and substitute values
            cp "$FRONTEND_DIR/.env.example" "$FRONTEND_ENV_FILE"
            
            # Replace placeholder values with actual CDK outputs
            sed -i.bak "s/VITE_AWS_REGION=.*/VITE_AWS_REGION=$AWS_REGION/" "$FRONTEND_ENV_FILE"
            sed -i.bak "s/VITE_USER_POOL_ID=.*/VITE_USER_POOL_ID=$USER_POOL_ID/" "$FRONTEND_ENV_FILE"
            sed -i.bak "s/VITE_USER_POOL_CLIENT_ID=.*/VITE_USER_POOL_CLIENT_ID=$USER_POOL_CLIENT_ID/" "$FRONTEND_ENV_FILE"
            sed -i.bak "s|VITE_GRAPHQL_API_URL=.*|VITE_GRAPHQL_API_URL=$GRAPHQL_API_URL|" "$FRONTEND_ENV_FILE"
            
            # Add deployment timestamp
            echo "" >> "$FRONTEND_ENV_FILE"
            echo "# Auto-configured by deploy.sh on $(date)" >> "$FRONTEND_ENV_FILE"
            
            rm -f "$FRONTEND_ENV_FILE.bak"
        else
            # Ultimate fallback: hardcoded template
            print_error ".env.example not found, using hardcoded template"
            cat > "$FRONTEND_ENV_FILE" << EOF
# Auto-generated by deploy.sh on $(date)

# AWS Configuration
VITE_AWS_REGION=$AWS_REGION

# Cognito Configuration
VITE_USER_POOL_ID=$USER_POOL_ID
VITE_USER_POOL_CLIENT_ID=$USER_POOL_CLIENT_ID

# GraphQL API
VITE_GRAPHQL_API_URL=$GRAPHQL_API_URL

# App Configuration
VITE_APP_TITLE=Multi-Agent Customer Support
VITE_APP_VERSION=1.0.0
EOF
        fi
    fi
    
    print_success "Frontend configuration updated"
    print_info "  • AWS Region: $AWS_REGION"
    print_info "  • User Pool ID: $USER_POOL_ID"
    print_info "  • GraphQL API: $GRAPHQL_API_URL"
}

# Setup frontend
setup_frontend() {
    print_info "Setting up frontend..."
    
    cd "$FRONTEND_DIR"
    
    if [ ! -d "node_modules" ]; then
        print_info "Installing frontend dependencies..."
        npm install
    fi
    
    cd ..
    print_success "Frontend setup completed"
}

# Display summary
display_summary() {
    echo ""
    echo "=========================================="
    echo "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY"
    echo "=========================================="
    echo ""
    echo "📋 Configuration:"
    echo "  • AWS Region: $AWS_REGION"
    echo "  • User Pool ID: $USER_POOL_ID"
    echo "  • GraphQL API: $GRAPHQL_API_URL"
    echo "  • Frontend Config: $FRONTEND_ENV_FILE"
    echo ""
    echo "🔄 Streaming Components:"
    echo "  • GraphQL API ID: $GRAPHQL_API_ID"
    echo "  • Chat Messages Table: $CHAT_MESSAGES_TABLE"
    echo "  • DynamoDB Streams: Enabled"
    echo "  • Stream Processor Lambda: Deployed"
    echo ""
    echo "🚀 Next Steps:"
    echo "  • Start frontend: cd frontend && npm run dev"
    echo "  • Test streaming: Send a chat message and watch real-time updates"
    echo "  • View logs: Check AWS CloudWatch for Lambda logs"
    echo "  • Monitor: Check DynamoDB streams and AppSync subscriptions"
    echo ""
}

# Main execution
main() {
    print_info "Starting deployment with AWS region: $AWS_REGION"
    clean_build_artifacts
    check_prerequisites
    deploy_infrastructure
    validate_streaming_components
    update_frontend_config
    setup_frontend
    display_summary
}

# Run with error handling
trap 'print_error "Deployment failed at line $LINENO"' ERR
main "$@"
