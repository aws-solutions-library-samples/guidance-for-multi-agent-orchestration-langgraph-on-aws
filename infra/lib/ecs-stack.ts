import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as servicediscovery from 'aws-cdk-lib/aws-servicediscovery';
import { Construct } from 'constructs';
import * as path from 'path';
import { DockerImageAsset, Platform } from 'aws-cdk-lib/aws-ecr-assets';

export interface EcsStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  ecsSecurityGroup: ec2.SecurityGroup;
  databaseSecret: secretsmanager.Secret;
  targetGroups: Map<string, elbv2.ApplicationTargetGroup>;
}

export interface AgentConfig {
  name: string;
  port: number;
  cpu: number;
  memory: number;
  desiredCount: number;
  dockerContext: string;
  dockerfile: string;
}

export class EcsStack extends cdk.Stack {
  public readonly ecsServices: Map<string, ecs.FargateService> = new Map();
  public readonly ecsClusters: Map<string, ecs.Cluster> = new Map();
  public readonly ecrRepositories: Map<string, ecr.Repository> = new Map();
  public readonly cloudMapNamespace: servicediscovery.PrivateDnsNamespace;

  private readonly agentConfigs: AgentConfig[] = [
    {
      name: 'supervisor',
      port: 8000,
      cpu: 512,
      memory: 1024,
      desiredCount: 2,
      dockerContext: path.join(__dirname, '../../agents/supervisor-agent'),
      dockerfile: 'Dockerfile',
    },
    {
      name: 'order-management',
      port: 8001,
      cpu: 512,
      memory: 1024,
      desiredCount: 2,
      dockerContext: path.join(__dirname, '../../agents/order-management-agent'),
      dockerfile: 'Dockerfile',
    },
    {
      name: 'product-recommendation',
      port: 8002,
      cpu: 512,
      memory: 1024,
      desiredCount: 2,
      dockerContext: path.join(__dirname, '../../agents/product-recommendation-agent'),
      dockerfile: 'Dockerfile',
    },
    {
      name: 'personalization',
      port: 8003,
      cpu: 256,
      memory: 512,
      desiredCount: 1,
      dockerContext: path.join(__dirname, '../../agents/personalization-agent'),
      dockerfile: 'Dockerfile',
    },
    {
      name: 'troubleshooting',
      port: 8004,
      cpu: 256,
      memory: 512,
      desiredCount: 1,
      dockerContext: path.join(__dirname, '../../agents/troubleshooting-agent'),
      dockerfile: 'Dockerfile',
    },
  ];

  constructor(scope: Construct, id: string, props: EcsStackProps) {
    super(scope, id, props);

    const { vpc, ecsSecurityGroup, databaseSecret, targetGroups } = props;

    // Create Cloud Map namespace for service discovery
    this.cloudMapNamespace = new servicediscovery.PrivateDnsNamespace(this, 'MultiAgentNamespace', {
      name: 'multi-agent.local',
      vpc,
      description: 'Service discovery namespace for multi-agent system',
    });

    // Create ECS Task Execution Role
    const taskExecutionRole = new iam.Role(this, 'ECSTaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });

    // Add permissions to read secrets
    taskExecutionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret',
        ],
        resources: [databaseSecret.secretArn],
      })
    );

    // Add permissions to call Amazon Bedrock
    taskExecutionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
          'bedrock:GetFoundationModel',
          'bedrock:ListFoundationModels',
        ],
        resources: ['*'],
      })
    );

    // Create ECS Task Role for application permissions
    const taskRole = new iam.Role(this, 'ECSTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });

    // Add permissions for CloudWatch logs
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:CreateLogGroup',
          'logs:CreateLogStream',
          'logs:PutLogEvents',
          'logs:DescribeLogStreams',
        ],
        resources: ['*'],
      })
    );

    // Add permissions to call Amazon Bedrock from application code
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
          'bedrock:GetFoundationModel',
          'bedrock:ListFoundationModels',
        ],
        resources: ['*'],
      })
    );

    // Add permissions for service discovery
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'servicediscovery:DiscoverInstances',
          'servicediscovery:GetService',
          'servicediscovery:ListServices',
          'servicediscovery:ListInstances',
        ],
        resources: ['*'],
      })
    );

    // Create ECR repositories and ECS infrastructure for each agent
    this.agentConfigs.forEach((agentConfig) => {
      this.createAgentInfrastructure(
        agentConfig,
        vpc,
        ecsSecurityGroup,
        taskExecutionRole,
        taskRole,
        databaseSecret,
        targetGroups,
        this.cloudMapNamespace
      );
    });

    // Output Cloud Map namespace information
    new cdk.CfnOutput(this, 'CloudMapNamespace', {
      value: this.cloudMapNamespace.namespaceName,
      description: 'Cloud Map namespace for service discovery',
      exportName: `${this.stackName}-CloudMapNamespace`,
    });

    new cdk.CfnOutput(this, 'CloudMapNamespaceId', {
      value: this.cloudMapNamespace.namespaceId,
      description: 'Cloud Map namespace ID',
      exportName: `${this.stackName}-CloudMapNamespaceId`,
    });

    // Output service discovery endpoints
    this.agentConfigs.forEach((agentConfig) => {
      new cdk.CfnOutput(this, `${this.toPascalCase(agentConfig.name)}ServiceEndpoint`, {
        value: `${agentConfig.name}.multi-agent.local:${agentConfig.port}`,
        description: `Service discovery endpoint for ${agentConfig.name} agent`,
        exportName: `${this.stackName}-${this.toPascalCase(agentConfig.name)}ServiceEndpoint`,
      });
    });

    // Output ECR repository URIs
    this.agentConfigs.forEach((agentConfig) => {
      const repository = this.ecrRepositories.get(agentConfig.name);
      if (repository) {
        new cdk.CfnOutput(this, `${this.toPascalCase(agentConfig.name)}ECRRepository`, {
          value: repository.repositoryUri,
          description: `ECR repository URI for ${agentConfig.name} agent`,
          exportName: `${this.stackName}-${this.toPascalCase(agentConfig.name)}ECRRepository`,
        });
      }
    });

    // Output Docker image URIs (these will be automatically pushed during deployment)
    this.agentConfigs.forEach((agentConfig) => {
      new cdk.CfnOutput(this, `${this.toPascalCase(agentConfig.name)}DockerImageUri`, {
        value: `Auto-built and pushed during deployment for ${agentConfig.name} agent`,
        description: `Docker image URI for ${agentConfig.name} agent (built from ${agentConfig.dockerContext})`,
        exportName: `${this.stackName}-${this.toPascalCase(agentConfig.name)}DockerImageUri`,
      });
    });

    // Output ECS cluster ARNs
    this.agentConfigs.forEach((agentConfig) => {
      const cluster = this.ecsClusters.get(agentConfig.name);
      if (cluster) {
        new cdk.CfnOutput(this, `${this.toPascalCase(agentConfig.name)}ClusterArn`, {
          value: cluster.clusterArn,
          description: `ECS cluster ARN for ${agentConfig.name} agent`,
          exportName: `${this.stackName}-${this.toPascalCase(agentConfig.name)}ClusterArn`,
        });
      }
    });
  }

  private createAgentInfrastructure(
    agentConfig: AgentConfig,
    vpc: ec2.Vpc,
    ecsSecurityGroup: ec2.SecurityGroup,
    taskExecutionRole: iam.Role,
    taskRole: iam.Role,
    databaseSecret: secretsmanager.Secret,
    targetGroups: Map<string, elbv2.ApplicationTargetGroup>,
    cloudMapNamespace: servicediscovery.PrivateDnsNamespace
  ): void {
    const { name, port, cpu, memory, desiredCount, dockerContext, dockerfile } = agentConfig;

    // Create ECR repository
    const repository = new ecr.Repository(this, `${this.toPascalCase(name)}Repository`, {
      repositoryName: `multi-agent-system/${name}-agent`,
      imageScanOnPush: true,
      lifecycleRules: [
        {
          description: 'Keep last 10 images',
          maxImageCount: 10,
        },
      ],
    });

    this.ecrRepositories.set(name, repository);

    // Build Docker image from source and automatically push to ECR
    const dockerImageAsset = new DockerImageAsset(this, `${this.toPascalCase(name)}DockerImage`, {
      directory: dockerContext,
      file: dockerfile,
      platform: Platform.LINUX_AMD64,
      buildArgs: {
        AGENT_NAME: name,
        AGENT_PORT: port.toString(),
      },
      // Ensure the image is built before proceeding
      invalidation: {
        buildArgs: true,
        file: true,
      },
    });

    // Use the built Docker image asset
    const containerImage = ecs.ContainerImage.fromDockerImageAsset(dockerImageAsset);

    // Create ECS Cluster
    const cluster = new ecs.Cluster(this, `${this.toPascalCase(name)}Cluster`, {
      clusterName: `${name}-cluster`,
      vpc,
      containerInsights: true,
    });

    this.ecsClusters.set(name, cluster);

    // Create CloudWatch Log Group
    const logGroup = new logs.LogGroup(this, `${this.toPascalCase(name)}LogGroup`, {
      logGroupName: `/aws/ecs/${name}-agent`,
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create Task Definition
    const taskDefinition = new ecs.FargateTaskDefinition(this, `${this.toPascalCase(name)}TaskDefinition`, {
      family: `${name}-agent-task`,
      cpu,
      memoryLimitMiB: memory,
      executionRole: taskExecutionRole,
      taskRole,
    });

    // Add container to task definition
    const container = taskDefinition.addContainer(`${this.toPascalCase(name)}Container`, {
      containerName: `${name}-agent`,
      image: containerImage, // Use the DockerImageAsset
      portMappings: [
        {
          containerPort: port,
          protocol: ecs.Protocol.TCP,
        },
      ],
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: `${name}-agent`,
        logGroup,
      }),
      environment: {
        AGENT_NAME: name,
        AGENT_PORT: port.toString(),
        ENVIRONMENT: this.node.tryGetContext('environment') || 'dev',
        AWS_DEFAULT_REGION: this.region,
        // Service discovery configuration
        SERVICE_DISCOVERY_NAMESPACE: 'multi-agent.local',
        // Service endpoints for discovery
        ORDER_MANAGEMENT_SERVICE: 'order-management.multi-agent.local:8001',
        PRODUCT_RECOMMENDATION_SERVICE: 'product-recommendation.multi-agent.local:8002',
        PERSONALIZATION_SERVICE: 'personalization.multi-agent.local:8003',
        TROUBLESHOOTING_SERVICE: 'troubleshooting.multi-agent.local:8004',
      },
      secrets: {
        DATABASE_URL: ecs.Secret.fromSecretsManager(databaseSecret, 'engine'),
        DATABASE_HOST: ecs.Secret.fromSecretsManager(databaseSecret, 'host'),
        DATABASE_PORT: ecs.Secret.fromSecretsManager(databaseSecret, 'port'),
        DATABASE_NAME: ecs.Secret.fromSecretsManager(databaseSecret, 'dbname'),
        DATABASE_USERNAME: ecs.Secret.fromSecretsManager(databaseSecret, 'username'),
        DATABASE_PASSWORD: ecs.Secret.fromSecretsManager(databaseSecret, 'password'),
      },
      // Health checks disabled to allow easier debugging and log viewing
      // healthCheck: {
      //   command: ['CMD-SHELL', `curl -f http://localhost:${port}/health || exit 1`],
      //   interval: cdk.Duration.seconds(30),
      //   timeout: cdk.Duration.seconds(5),
      //   retries: 1,
      //   startPeriod: cdk.Duration.seconds(60),
      // },
    });

    // Create ECS Service with Cloud Map service discovery
    const service = new ecs.FargateService(this, `${this.toPascalCase(name)}Service`, {
      serviceName: `${name}-service`,
      cluster,
      taskDefinition,
      desiredCount,
      securityGroups: [ecsSecurityGroup],
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      // enableLogging: true,
      // healthCheckGracePeriod: cdk.Duration.seconds(60), // Disabled to allow easier debugging
      enableExecuteCommand: true, // For debugging
      // Deployment configuration to ensure proper rollout
      maxHealthyPercent: 200,
      minHealthyPercent: 50, // Allow more flexibility during deployments
      circuitBreaker: {
        rollback: false, // Disable rollback to keep tasks running for debugging
      },
      // Add Cloud Map service discovery
      cloudMapOptions: {
        name: name, // Service name in Cloud Map (e.g., 'supervisor', 'order-management')
        cloudMapNamespace: cloudMapNamespace,
        dnsRecordType: servicediscovery.DnsRecordType.A,
        dnsTtl: cdk.Duration.seconds(60),
        failureThreshold: 1,
        containerPort: port, // Port for service discovery
      },
    });

    // Configure Auto Scaling
    const scalableTarget = service.autoScaleTaskCount({
      minCapacity: 1,
      maxCapacity: desiredCount * 3,
    });

    // Scale based on CPU utilization
    scalableTarget.scaleOnCpuUtilization(`${this.toPascalCase(name)}CpuScaling`, {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(300),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Scale based on memory utilization
    scalableTarget.scaleOnMemoryUtilization(`${this.toPascalCase(name)}MemoryScaling`, {
      targetUtilizationPercent: 80,
      scaleInCooldown: cdk.Duration.seconds(300),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Attach service to target group only for supervisor agent
    const targetGroup = targetGroups.get(name);
    if (targetGroup && name === 'supervisor') {
      service.attachToApplicationTargetGroup(targetGroup);
    }

    this.ecsServices.set(name, service);

    // Add explicit dependency to ensure proper order
    // The service depends on the Docker image being built and available
    service.node.addDependency(taskDefinition);
    taskDefinition.node.addDependency(dockerImageAsset);
  }

  private toPascalCase(str: string): string {
    return str
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
  }
}
