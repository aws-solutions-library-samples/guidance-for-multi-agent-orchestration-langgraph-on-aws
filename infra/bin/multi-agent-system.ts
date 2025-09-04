#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { NetworkStack } from '../lib/network-stack';
import { DatabaseStack } from '../lib/database-stack';
import { EcsStack } from '../lib/ecs-stack';
import { LoadBalancerStack } from '../lib/load-balancer-stack';
import { MonitoringStack } from '../lib/monitoring-stack';
import { StreamingApiStack } from '../lib/streaming-api-stack';
import { BedrockKnowledgeBaseStack } from '../lib/bedrock-knowledge-base-stack';
import { FrontendStack } from '../lib/frontend-stack';

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
  lambdaSecurityGroup: networkStack.lambdaSecurityGroup,
  description: 'Load balancer infrastructure for multi-agent system',
  stackName: `${stackPrefix}-LoadBalancer-${environment}`,
});

// Bedrock Knowledge Base Stack - Vector DB and Knowledge Base
const bedrockKnowledgeBaseStack = new BedrockKnowledgeBaseStack(app, `${stackPrefix}-BedrockKB-${environment}`, {
  env,
  vpc: networkStack.vpc,
  environment,
  description: 'Bedrock Knowledge Base for unstructured data',
  stackName: `${stackPrefix}-BedrockKB-${environment}`,
});

// ECS Stack - Clusters, Services, Task Definitions
const ecsStack = new EcsStack(app, `${stackPrefix}-ECS-${environment}`, {
  env,
  vpc: networkStack.vpc,
  ecsSecurityGroup: networkStack.ecsSecurityGroup,
  databaseSecret: databaseStack.databaseSecret,
  databaseClusterArn: databaseStack.database.clusterArn,
  targetGroups: loadBalancerStack.targetGroups,
  personalizationKnowledgeBaseId: bedrockKnowledgeBaseStack.personalizationKnowledgeBase.attrKnowledgeBaseId,
  troubleshootingKnowledgeBaseId: bedrockKnowledgeBaseStack.troubleshootingKnowledgeBase.attrKnowledgeBaseId,
  description: 'ECS infrastructure for multi-agent system',
  stackName: `${stackPrefix}-ECS-${environment}`,
});



// Streaming API Stack - AppSync GraphQL API
const streamingApiStack = new StreamingApiStack(app, `${stackPrefix}-StreamingAPI-${environment}`, {
  env,
  vpc: networkStack.vpc,
  ecsSecurityGroup: networkStack.ecsSecurityGroup,
  lambdaSecurityGroup: networkStack.lambdaSecurityGroup,
  environment,
  supervisorAgentUrl: `http://${loadBalancerStack.loadBalancer.loadBalancerDnsName}`,
  description: 'AppSync GraphQL API for multi-agent system',
  stackName: `${stackPrefix}-StreamingAPI-${environment}`,
});

// Frontend Stack - React application hosting with S3 and CloudFront
const frontendStack = new FrontendStack(app, `${stackPrefix}-Frontend-${environment}`, {
  env,
  environment,
  streamingApiStackName: `${stackPrefix}-StreamingAPI-${environment}`,
  description: 'Frontend infrastructure for multi-agent system',
  stackName: `${stackPrefix}-Frontend-${environment}`,
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
bedrockKnowledgeBaseStack.addDependency(networkStack);
ecsStack.addDependency(databaseStack);
ecsStack.addDependency(loadBalancerStack);
ecsStack.addDependency(bedrockKnowledgeBaseStack);
streamingApiStack.addDependency(networkStack);
streamingApiStack.addDependency(loadBalancerStack);
frontendStack.addDependency(streamingApiStack); // Frontend needs StreamingAPI outputs
monitoringStack.addDependency(ecsStack);

// Add tags to all stacks
const stacks = [networkStack, databaseStack, ecsStack, loadBalancerStack, bedrockKnowledgeBaseStack, streamingApiStack, frontendStack, monitoringStack];
stacks.forEach(stack => {
  cdk.Tags.of(stack).add('Project', 'MultiAgentSystem');
  cdk.Tags.of(stack).add('Environment', environment);
  cdk.Tags.of(stack).add('ManagedBy', 'CDK');
});

app.synth();
