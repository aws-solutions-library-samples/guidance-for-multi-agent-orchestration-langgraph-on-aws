# ECS Multi-Agent Integration with AppSync - Infrastructure Setup Guide

## Overview

This guide will help you set up AppSync GraphQL API infrastructure to connect to your existing ECS-based multi-agent system.

**Target Architecture**: Frontend → AppSync → Lambda → Your Existing ECS Supervisor → Your Existing ECS Sub-agents


## Phase 1: Infrastructure Foundation

### 1.1 VPC Configuration Analysis

**Action**: Document your existing ECS setup:
- VPC ID where ECS services are running
- Private subnets used by ECS services
- Security groups for ECS services
- Load balancer configuration (if any)
- Service discovery setup (if any)

### 1.2 Networking Requirements

**Action**: Ensure the following network connectivity:
- Lambda can reach ECS supervisor service
- ECS services can reach DynamoDB (for chat storage)
- Appropriate security group rules for HTTP communication

## Phase 2: AppSync GraphQL API Setup

### 2.1 Create AppSync API with CDK

**New File**: `infra/lib/streaming-api/index.ts`

**Purpose**: Set up AppSync with:
- Cognito user pool authentication
- GraphQL schema definitions
- Lambda data sources
- DynamoDB integration for chat storage

### 2.2 GraphQL Schema Design

**New File**: `infra/lib/streaming-api/schema.graphql`

**Action**: Define GraphQL schema with:
- Chat and Session models for DynamoDB
- Mutations for interacting with your agents
- Queries for retrieving agent status and data
- Subscriptions for real-time updates

**Key Operations**:
- `sendChat` - Send message to supervisor agent
- `executeTaskOnAgent` - Direct agent task execution
- `aggregateDataFromAgents` - Multi-agent data collection
- `getAgentStatus` - Agent health monitoring

## Phase 3: Lambda Resolver Implementation

### 3.1 Create Lambda Resolver Function

**New File**: `infra/lib/streaming-api/resolver-function/index.ts`

**Purpose**: Create Lambda function that:
- Routes GraphQL operations to appropriate handlers
- Communicates with your existing supervisor agent via HTTP
- Handles authentication and authorization
- Manages DynamoDB operations for chat storage

### 3.2 Agent Communication Module

**New File**: `infra/lib/streaming-api/resolver-function/agentClient.ts`

**Purpose**: Implement HTTP client for:
- Connecting to your existing supervisor agent
- Circuit breaker pattern for reliability
- Connection pooling for performance
- Error handling and retries

### 3.3 Environment Configuration

**Action**: Configure Lambda with environment variables:
- `SUPERVISOR_AGENT_URL` - Your existing supervisor endpoint
- `GRAPH_API_URL` - AppSync GraphQL URL
- `SUB_AGENT_URLS` - JSON mapping of your sub-agent endpoints (if direct access needed)

## Phase 4: Network Integration

### 4.1 Lambda VPC Configuration

**Action**: Configure Lambda to run in the same VPC as your ECS services:
- Place Lambda in private subnets
- Ensure NAT gateway access for DynamoDB
- Configure security groups for ECS communication

### 4.2 Service Discovery Integration

**Action**: If your ECS services use service discovery:
- Integrate Lambda with AWS Cloud Map
- Use service discovery for dynamic endpoint resolution
- Configure DNS resolution within VPC

### 4.3 Load Balancer Integration

**Action**: If your supervisor uses ALB:
- Configure Lambda to communicate through ALB
- Set up health checks and proper routing
- Handle load balancer target group configuration

## Phase 6: Security Configuration

### 6.1 Cognito Authentication

**Action**: Set up Cognito integration:
- User pool for authentication
- App client configuration
- JWT token validation in AppSync
- User-specific data access patterns

### 6.2 IAM Permissions

**Action**: Configure IAM roles for:
- Lambda execution role with VPC access
- DynamoDB read/write permissions
- CloudWatch logging permissions
- Network interface management

### 6.3 WAF Protection

**Action**: Set up WAF for AppSync:
- Rate limiting rules
- IP-based restrictions
- Request size limits
- SQL injection protection

## Phase 7: Real-time Features

### 7.1 GraphQL Subscriptions

**Action**: Implement subscriptions for:
- Real-time chat updates
- Agent status changes
- Task completion notifications
- Error alerts

### 7.2 Streaming Response Handling

**Action**: Configure streaming for:
- Long-running agent tasks
- Real-time response from supervisor
- Progressive result updates
- WebSocket connection management

## Phase 8: Monitoring and Observability

### 8.1 CloudWatch Integration

**Action**: Set up monitoring for:
- Lambda function performance
- AppSync operation metrics
- DynamoDB usage patterns
- Network latency measurements

### 8.2 X-Ray Tracing

**Action**: Enable distributed tracing:
- Lambda function tracing
- HTTP calls to ECS services
- DynamoDB operation tracing
- End-to-end request flow

### 8.3 Alerting Setup

**Action**: Configure alerts for:
- ECS agent connectivity issues
- Lambda function errors
- AppSync operation failures
- Circuit breaker activations

## Phase 9: Testing and Validation

### 9.1 Unit Testing

**New File**: `infra/lib/streaming-api/resolver-function/testHelper.ts`

**Action**: Create tests for:
- Agent client HTTP communication
- GraphQL resolver functions
- Error handling scenarios
- Circuit breaker behavior

### 9.2 Integration Testing

**Action**: Test complete flows:
- Frontend → AppSync → Lambda → Your ECS Supervisor
- Real-time subscriptions
- Multi-agent aggregation
- Error recovery scenarios
