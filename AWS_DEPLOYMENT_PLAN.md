# AWS Multi-Agent System Deployment Plan

## Overview
This plan outlines the deployment of a multi-agent customer support system on AWS, where each agent runs in its own dedicated ECS Fargate cluster for isolation, scalability, and independent management.

## Bedrock Model Configuration

### Claude 3.7 Sonnet Cross-Region Inference Profiles
The system is configured to use Claude 3.7 Sonnet cross-region inference profiles for optimal performance:

**Automatic Region Selection:**
- **EU Deployments**: Uses `eu.anthropic.claude-3-7-sonnet-20250219-v1:0`
  - Routes across: eu-central-1, eu-north-1, eu-west-1, eu-west-3
- **US Deployments**: Uses `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
  - Routes across: us-east-1, us-east-2, us-west-2

**Configuration Method:**
- Automatically determined by `AWS_DEFAULT_REGION` environment variable
- Can be overridden using `BEDROCK_MODEL_ID` environment variable
- All agents inherit the same model configuration for consistency

**Benefits:**
- Higher request limits for multi-agent workflows
- Cross-region routing for improved availability
- Eliminates throttling issues during concurrent agent operations

## Architecture Components

### 1. Network Infrastructure
- **VPC**: Dedicated Virtual Private Cloud with CIDR 10.0.0.0/16
- **Subnets**: 
  - 2 Public subnets (10.0.1.0/24, 10.0.2.0/24) for load balancers
  - 2 Private subnets (10.0.10.0/24, 10.0.20.0/24) for ECS tasks
- **Internet Gateway**: For public internet access
- **NAT Gateways**: For outbound internet access from private subnets
- **Route Tables**: Proper routing for public and private subnets

### 2. ECS Clusters (One per Agent)

#### Agent Clusters:
1. **Order Management Agent Cluster**
   - Cluster Name: `order-management-cluster`
   - Service Name: `order-management-service`
   - Port: 8001

2. **Product Recommendation Agent Cluster**
   - Cluster Name: `product-recommendation-cluster`
   - Service Name: `product-recommendation-service`
   - Port: 8002

3. **Personalization Agent Cluster**
   - Cluster Name: `personalization-cluster`
   - Service Name: `personalization-service`
   - Port: 8003

4. **Troubleshooting Agent Cluster**
   - Cluster Name: `troubleshooting-cluster`
   - Service Name: `troubleshooting-service`
   - Port: 8004

5. **Supervisor Agent Cluster**
   - Cluster Name: `supervisor-cluster`
   - Service Name: `supervisor-service`
   - Port: 8000

#### ECS Configuration per Cluster:
- **Launch Type**: Fargate
- **CPU**: 512 (0.5 vCPU) - adjustable per agent needs
- **Memory**: 1024 MB (1 GB) - adjustable per agent needs
- **Desired Count**: 2 tasks per service (for high availability)
- **Health Check**: HTTP health check on `/health` endpoint
- **Auto Scaling**: Target tracking based on CPU utilization (70% threshold)

### 3. Load Balancing

#### Application Load Balancer (ALB)
- **Name**: `multi-agent-alb`
- **Scheme**: Internet-facing
- **Subnets**: Public subnets
- **Security Group**: Allow HTTP/HTTPS traffic

#### Target Groups (One per Agent):
1. `order-management-tg` → Port 8001
2. `product-recommendation-tg` → Port 8002
3. `personalization-tg` → Port 8003
4. `troubleshooting-tg` → Port 8004
5. `supervisor-tg` → Port 8000

#### Routing Rules:
- `/order/*` → Order Management Agent
- `/product/*` → Product Recommendation Agent
- `/personalization/*` → Personalization Agent
- `/troubleshooting/*` → Troubleshooting Agent
- `/supervisor/*` or `/` → Supervisor Agent

### 4. Database Layer

#### Aurora PostgreSQL Serverless v2
- **Engine**: Aurora PostgreSQL 15.3
- **Configuration**: Pure Serverless v2 (0.5-4 ACUs)
- **Multi-AZ**: Yes (for production)
- **Storage**: Auto-scaling, encrypted
- **Backup**: 7-day retention
- **Subnets**: Private subnets only
- **Security Group**: Allow access only from ECS tasks
- **RDS Data API**: Enabled for serverless database access

#### Database Schema:
- Migrated from SQLite `order_management.db` to Aurora PostgreSQL
- Shared database for all agents with proper table isolation
- RDS Data API for connection-less database access

### 5. Security

#### IAM Roles:
1. **ECS Task Execution Role**: For pulling images and logging
2. **ECS Task Role**: For application-specific AWS service access
3. **RDS Access Role**: For database connections

#### Security Groups:
1. **ALB Security Group**: 
   - Inbound: HTTP (80), HTTPS (443) from 0.0.0.0/0
   - Outbound: All traffic to ECS security group

2. **ECS Security Group**:
   - Inbound: HTTP from ALB security group
   - Outbound: All traffic (for external API calls)

3. **RDS Security Group**:
   - Inbound: PostgreSQL (5432) from ECS security group
   - Outbound: None

#### Secrets Management:
- **AWS Secrets Manager**: Store database credentials, API keys
- **Environment Variables**: Non-sensitive configuration

### 6. Monitoring and Logging

#### CloudWatch Logs:
- Log Group per agent: `/aws/ecs/[agent-name]`
- Log retention: 30 days
- Structured logging with JSON format

#### CloudWatch Metrics:
- ECS service metrics (CPU, Memory, Task count)
- ALB metrics (Request count, Response time, Error rate)
- RDS metrics (Connections, CPU, Storage)

#### CloudWatch Alarms:
- High CPU utilization (>80%)
- High memory utilization (>80%)
- Service task count below desired
- Database connection failures
- ALB 5xx error rate threshold

### 7. Container Images

#### ECR Repositories (One per Agent):
1. `order-management-agent`
2. `product-recommendation-agent`
3. `personalization-agent`
4. `troubleshooting-agent`
5. `supervisor-agent`

#### Docker Image Strategy:
- Base image: `python:3.11-slim`
- Multi-stage builds for smaller images
- Security scanning enabled
- Lifecycle policies for image cleanup

### 8. Deployment Strategy

#### Blue/Green Deployment:
- Use ECS service deployment configuration
- Rolling updates with 50% replacement
- Health check grace period: 60 seconds
- Deployment timeout: 10 minutes

#### CI/CD Pipeline (Future Enhancement):
- AWS CodePipeline + CodeBuild
- Automated testing and deployment
- Environment promotion (dev → staging → prod)

## Resource Sizing and Costs

### Development Environment:
- **ECS Tasks**: 5 clusters × 1 task × 0.5 vCPU × 1GB RAM
- **RDS**: db.t3.micro
- **ALB**: 1 Application Load Balancer
- **Estimated Monthly Cost**: ~$150-200

### Production Environment:
- **ECS Tasks**: 5 clusters × 2 tasks × 1 vCPU × 2GB RAM
- **RDS**: db.t3.small with Multi-AZ
- **ALB**: 1 Application Load Balancer with higher throughput
- **Estimated Monthly Cost**: ~$400-600

## Deployment Steps

### Phase 1: Infrastructure Setup
1. Deploy VPC and networking components
2. Create ECR repositories
3. Set up RDS instance
4. Configure IAM roles and security groups

### Phase 2: Container Preparation
1. Create Dockerfiles for each agent
2. Build and push images to ECR
3. Test images locally

### Phase 3: ECS Deployment
1. Create ECS clusters
2. Define task definitions
3. Create services with auto-scaling
4. Configure load balancer and target groups

### Phase 4: Testing and Monitoring
1. Deploy monitoring and alerting
2. Perform end-to-end testing
3. Load testing and performance tuning
4. Security testing and compliance checks

## High Availability and Disaster Recovery

### High Availability:
- Multi-AZ deployment across 2 availability zones
- Auto Scaling Groups for ECS services
- RDS Multi-AZ for database failover
- Health checks and automatic task replacement

### Disaster Recovery:
- RDS automated backups and point-in-time recovery
- Cross-region ECR image replication
- Infrastructure as Code for quick environment recreation
- Database backup strategy with 7-day retention

## Security Best Practices

1. **Network Security**: Private subnets for ECS tasks and RDS
2. **Encryption**: At-rest and in-transit encryption for all data
3. **Access Control**: Least privilege IAM policies
4. **Secrets Management**: No hardcoded credentials
5. **Container Security**: Regular image scanning and updates
6. **Monitoring**: Comprehensive logging and alerting

## Scalability Considerations

### Horizontal Scaling:
- Auto Scaling based on CPU/memory metrics
- Independent scaling per agent based on demand
- Load balancer automatically distributes traffic

### Vertical Scaling:
- Easy task definition updates for CPU/memory
- RDS instance class can be modified with minimal downtime

### Performance Optimization:
- Connection pooling for database connections
- Caching strategies at application level
- CDN for static content (if applicable)

## Next Steps

1. Review and approve this deployment plan
2. Create CDK infrastructure code
3. Prepare Docker containers for each agent
4. Set up CI/CD pipeline
5. Deploy to development environment first
6. Perform testing and optimization
7. Deploy to production environment

This plan provides a robust, scalable, and secure foundation for your multi-agent system on AWS while maintaining clear separation of concerns and independent scaling capabilities for each agent.
