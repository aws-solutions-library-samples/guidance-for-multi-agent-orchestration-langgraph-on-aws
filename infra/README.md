# Multi-Agent System Infrastructure

This directory contains AWS CDK code written in TypeScript to deploy a multi-agent customer support system on AWS.

## Architecture Overview

The infrastructure consists of:
- **5 ECS Fargate clusters** (one per agent)
- **Application Load Balancer** with path-based routing
- **Aurora PostgreSQL database cluster** for shared data with read replicas
- **ECR repositories** for container images
- **CloudWatch monitoring** with alarms and dashboards
- **VPC with public/private subnets** for network isolation

## Agents

1. **Supervisor Agent** (Port 8000) - Routes: `/`, `/supervisor/*`
2. **Order Management Agent** (Port 8001) - Route: `/order/*`
3. **Product Recommendation Agent** (Port 8002) - Route: `/product/*`
4. **Personalization Agent** (Port 8003) - Route: `/personalization/*`
5. **Troubleshooting Agent** (Port 8004) - Route: `/troubleshooting/*`

## Prerequisites

1. **Node.js** (v16 or later)
2. **AWS CLI** configured with appropriate credentials
3. **AWS CDK CLI** installed globally: `npm install -g aws-cdk`
4. **Docker** for building container images

## Setup Instructions

### 1. Install Dependencies

```bash
cd infra
npm install
```

### 2. Configure AWS Environment

```bash
# Set your AWS account and region
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-east-1

# Or configure AWS CLI
aws configure
```

### 3. Bootstrap CDK (First time only)

```bash
cdk bootstrap
```

### 4. Build and Deploy

```bash
# Build TypeScript
npm run build

# Review what will be deployed
cdk diff

# Deploy all stacks
npm run deploy

# Or deploy individual stacks
cdk deploy MultiAgentSystem-Network-dev
cdk deploy MultiAgentSystem-Database-dev
cdk deploy MultiAgentSystem-ECS-dev
cdk deploy MultiAgentSystem-LoadBalancer-dev
cdk deploy MultiAgentSystem-Monitoring-dev
```

## Environment Configuration

You can deploy to different environments by setting the context:

```bash
# Deploy to development (default)
cdk deploy --context environment=dev

# Deploy to staging
cdk deploy --context environment=staging

# Deploy to production
cdk deploy --context environment=prod
```

## Container Images

The CDK deployment automatically builds and pushes Docker images for each agent during deployment. Each agent directory should contain:

- `Dockerfile` - Container definition
- `requirements.txt` - Python dependencies
- `app.py` - Main application file
- Other agent-specific files

### Agent Directory Structure
```
agents/
├── supervisor-agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── ...
├── order-management-agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── ...
└── ... (other agents)
```

### Automatic Build Process

During `cdk deploy`, the following happens automatically:
1. Docker images are built from each agent's directory
2. Images are tagged and pushed to their respective ECR repositories
3. ECS task definitions are created with the built images
4. ECS services are deployed with proper health checks

### Build Arguments

Each Dockerfile receives these build arguments:
- `AGENT_NAME` - The name of the agent
- `AGENT_PORT` - The port the agent should listen on

### Environment Variables

Each container receives these environment variables:
- `AGENT_NAME` - Agent identifier
- `AGENT_PORT` - Port number
- `ENVIRONMENT` - Deployment environment (dev/staging/prod)
- `AWS_DEFAULT_REGION` - AWS region
- Database connection details via AWS Secrets Manager

## Database Setup

The Aurora PostgreSQL cluster will be created automatically with:
- **Writer instance**: For write operations
- **Reader instance**: For read scaling and high availability
- **Serverless v2**: Auto-scaling between 0.5-2 ACU based on demand

To migrate your existing SQLite data:

1. Get database credentials from AWS Secrets Manager
2. Connect to the Aurora cluster writer endpoint
3. Create tables and migrate data from `order_management.db`

```bash
# Get database connection details
aws secretsmanager get-secret-value --secret-id <database-secret-arn>

# Connect to Aurora cluster
psql -h <cluster-endpoint> -U postgres -d multiagent
```

## Monitoring

After deployment, you can access:

1. **CloudWatch Dashboard**: Check the output for the dashboard URL
2. **ECS Services**: Monitor in AWS Console → ECS
3. **Load Balancer**: Check health checks in AWS Console → EC2 → Load Balancers
4. **RDS Database**: Monitor in AWS Console → RDS

## Scaling Configuration

Each agent is configured with auto-scaling based on:
- **CPU utilization**: Target 70%
- **Memory utilization**: Target 80%
- **Min capacity**: 1 task
- **Max capacity**: 3x desired count

To modify scaling settings, update the `ecs-stack.ts` file.

## Security Features

- **VPC**: Isolated network with public/private subnets
- **Security Groups**: Restrictive ingress/egress rules
- **IAM Roles**: Least privilege access
- **Secrets Manager**: Secure credential storage
- **Encryption**: At-rest and in-transit encryption enabled

## Cost Optimization

### Development Environment
- Aurora: Serverless v2 with 0.5-2 ACU auto-scaling
- ECS: 0.5 vCPU, 1GB RAM per task
- Estimated cost: ~$200-300/month

### Production Environment
- Aurora: Provisioned instances (t4g.medium writer + reader)
- ECS: 1 vCPU, 2GB RAM per task
- Estimated cost: ~$500-800/month

## Troubleshooting

### Common Issues

1. **ECS Tasks Not Starting**
   - Check CloudWatch logs: `/aws/ecs/[agent-name]`
   - Verify ECR image exists and is accessible
   - Check security group rules

2. **Load Balancer Health Checks Failing**
   - Ensure `/health` endpoint exists in your application
   - Check target group health in AWS Console
   - Verify security group allows ALB → ECS communication

3. **Database Connection Issues**
   - Check security group allows ECS → RDS communication
   - Verify database credentials in Secrets Manager
   - Check VPC DNS resolution

### Useful Commands

```bash
# View stack outputs
cdk list
cdk diff
cdk synth

# Check ECS service status
aws ecs describe-services --cluster supervisor-cluster --services supervisor-service

# View CloudWatch logs
aws logs describe-log-groups --log-group-name-prefix "/aws/ecs/"

# Check load balancer health
aws elbv2 describe-target-health --target-group-arn <target-group-arn>
```

## Cleanup

To destroy all resources:

```bash
# Destroy all stacks
npm run destroy

# Or destroy individual stacks (in reverse order)
cdk destroy MultiAgentSystem-Monitoring-dev
cdk destroy MultiAgentSystem-LoadBalancer-dev
cdk destroy MultiAgentSystem-ECS-dev
cdk destroy MultiAgentSystem-Database-dev
cdk destroy MultiAgentSystem-Network-dev
```

**Note**: Some resources like ECR repositories with images may need manual cleanup.

## Next Steps

1. Create Dockerfiles for each agent
2. Set up CI/CD pipeline for automated deployments
3. Configure SSL certificate for HTTPS
4. Set up custom domain name
5. Implement application-level monitoring
6. Configure log aggregation and analysis
7. Set up backup and disaster recovery procedures

## Support

For issues with the infrastructure deployment, check:
1. AWS CloudFormation console for stack events
2. CloudWatch logs for detailed error messages
3. AWS CDK documentation: https://docs.aws.amazon.com/cdk/
