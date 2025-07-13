#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { NetworkStack } from '../lib/network-stack';
import { DatabaseStack } from '../lib/database-stack';
import { EcsStack } from '../lib/ecs-stack';
import { LoadBalancerStack } from '../lib/load-balancer-stack';
import { MonitoringStack } from '../lib/monitoring-stack';
import { StreamingApiStack } from '../lib/streaming-api-stack';

const app = new cdk.App();

// Get environment configuration
const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

// Stack naming prefix
const stackPrefix = 'MultiAgentSystem';
const environment = app.node.tryGetContext('environment') || 'dev';

// Network Stack - VPC, Subnets, Security Groups
const networkStack = new NetworkStack(app, `${stackPrefix}-Network-${environment}`, {
  env,
  description: 'Network infrastructure for multi-agent system',
  stackName: `${stackPrefix}-Network-${environment}`,
});

// Database Stack - RDS PostgreSQL
const databaseStack = new DatabaseStack(app, `${stackPrefix}-Database-${environment}`, {
  env,
  vpc: networkStack.vpc,
  databaseSecurityGroup: networkStack.databaseSecurityGroup,
  description: 'Database infrastructure for multi-agent system',
  stackName: `${stackPrefix}-Database-${environment}`,
});

// Load Balancer Stack - ALB, Target Groups, Listeners (created before ECS)
const loadBalancerStack = new LoadBalancerStack(app, `${stackPrefix}-LoadBalancer-${environment}`, {
  env,
  vpc: networkStack.vpc,
  albSecurityGroup: networkStack.albSecurityGroup,
  description: 'Load balancer infrastructure for multi-agent system',
  stackName: `${stackPrefix}-LoadBalancer-${environment}`,
});

// ECS Stack - Clusters, Services, Task Definitions
const ecsStack = new EcsStack(app, `${stackPrefix}-ECS-${environment}`, {
  env,
  vpc: networkStack.vpc,
  ecsSecurityGroup: networkStack.ecsSecurityGroup,
  databaseSecret: databaseStack.databaseSecret,
  targetGroups: loadBalancerStack.targetGroups,
  description: 'ECS infrastructure for multi-agent system',
  stackName: `${stackPrefix}-ECS-${environment}`,
});

// Streaming API Stack - AppSync GraphQL API
const streamingApiStack = new StreamingApiStack(app, `${stackPrefix}-StreamingAPI-${environment}`, {
  env,
  vpc: networkStack.vpc,
  ecsSecurityGroup: networkStack.ecsSecurityGroup,
  environment,
  description: 'AppSync GraphQL API for multi-agent system',
  stackName: `${stackPrefix}-StreamingAPI-${environment}`,
});

// Monitoring Stack - CloudWatch, Alarms
const monitoringStack = new MonitoringStack(app, `${stackPrefix}-Monitoring-${environment}`, {
  env,
  ecsServices: ecsStack.ecsServices,
  loadBalancer: loadBalancerStack.loadBalancer,
  database: databaseStack.database,
  description: 'Monitoring infrastructure for multi-agent system',
  stackName: `${stackPrefix}-Monitoring-${environment}`,
});

// Add dependencies
databaseStack.addDependency(networkStack);
loadBalancerStack.addDependency(networkStack);
ecsStack.addDependency(databaseStack);
ecsStack.addDependency(loadBalancerStack);
streamingApiStack.addDependency(networkStack);
streamingApiStack.addDependency(ecsStack);
monitoringStack.addDependency(ecsStack);

// Add tags to all stacks
const stacks = [networkStack, databaseStack, ecsStack, loadBalancerStack, streamingApiStack, monitoringStack];
stacks.forEach(stack => {
  cdk.Tags.of(stack).add('Project', 'MultiAgentSystem');
  cdk.Tags.of(stack).add('Environment', environment);
  cdk.Tags.of(stack).add('ManagedBy', 'CDK');
});

app.synth();
