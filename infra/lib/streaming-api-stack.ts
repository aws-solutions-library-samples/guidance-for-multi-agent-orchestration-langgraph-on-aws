import * as cdk from 'aws-cdk-lib';
import * as appsync from 'aws-cdk-lib/aws-appsync';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

export interface StreamingApiStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  ecsSecurityGroup: ec2.SecurityGroup;
  lambdaSecurityGroup: ec2.SecurityGroup;
  environment: string;
  supervisorAgentUrl?: string;
}

export class StreamingApiStack extends cdk.Stack {
  public readonly graphqlApi: appsync.GraphqlApi;
  public readonly eventsApi: appsync.EventApi;
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly chatSessionsTable: dynamodb.Table;
  public readonly chatMessagesTable: dynamodb.Table;
  public readonly agentStatusTable: dynamodb.Table;
  public readonly checkpointsTable: dynamodb.Table;
  public readonly resolverFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: StreamingApiStackProps) {
    super(scope, id, props);

    // Create Cognito User Pool for authentication
    this.userPool = new cognito.UserPool(this, 'MultiAgentUserPool', {
      userPoolName: `multi-agent-user-pool-${props.environment}`,
      selfSignUpEnabled: true,
      signInAliases: {
        email: true,
        username: false,
      },
      autoVerify: {
        email: true,
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create User Pool Client
    this.userPoolClient = new cognito.UserPoolClient(this, 'MultiAgentUserPoolClient', {
      userPool: this.userPool,
      userPoolClientName: `multi-agent-client-${props.environment}`,
      generateSecret: false,
      authFlows: {
        userSrp: true,
        userPassword: true,
        adminUserPassword: true,
      },
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
          implicitCodeGrant: true,
        },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],
      },
    });

    // Create DynamoDB Tables
    this.chatSessionsTable = new dynamodb.Table(this, 'ChatSessionsTable', {
      tableName: `chat-sessions-${props.environment}`,
      partitionKey: {
        name: 'sessionId',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      // Add stream for real-time updates
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    // Add GSI for user-based queries with status filtering
    this.chatSessionsTable.addGlobalSecondaryIndex({
      indexName: 'UserIdIndex',
      partitionKey: {
        name: 'userId',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'createdAt',
        type: dynamodb.AttributeType.STRING,
      },
    });

    // Add GSI for status-based queries (active sessions)
    this.chatSessionsTable.addGlobalSecondaryIndex({
      indexName: 'StatusIndex',
      partitionKey: {
        name: 'status',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'lastActivity',
        type: dynamodb.AttributeType.STRING,
      },
    });

    this.chatMessagesTable = new dynamodb.Table(this, 'ChatMessagesTable', {
      tableName: `chat-messages-${props.environment}`,
      partitionKey: {
        name: 'sessionId',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'messageId',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      // Add stream for real-time message updates
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    // Add GSI for timestamp-based queries (chronological message ordering)
    this.chatMessagesTable.addGlobalSecondaryIndex({
      indexName: 'TimestampIndex',
      partitionKey: {
        name: 'sessionId',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
    });

    // Add GSI for user-based message queries across sessions
    this.chatMessagesTable.addGlobalSecondaryIndex({
      indexName: 'UserMessageIndex',
      partitionKey: {
        name: 'userId',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
    });

    this.agentStatusTable = new dynamodb.Table(this, 'AgentStatusTable', {
      tableName: `agent-status-${props.environment}`,
      partitionKey: {
        name: 'agentId',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      // Add stream for real-time agent status updates
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    // LangGraph Checkpoints Table for session persistence
    this.checkpointsTable = new dynamodb.Table(this, 'CheckpointsTable', {
      tableName: 'langgraph-checkpoints',
      partitionKey: {
        name: 'thread_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'checkpoint_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Add GSI for agent type queries with health status filtering
    this.agentStatusTable.addGlobalSecondaryIndex({
      indexName: 'AgentTypeIndex',
      partitionKey: {
        name: 'type',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'lastHeartbeat',
        type: dynamodb.AttributeType.STRING,
      },
    });

    // Add GSI for health status monitoring across all agents
    this.agentStatusTable.addGlobalSecondaryIndex({
      indexName: 'HealthStatusIndex',
      partitionKey: {
        name: 'status',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'lastHeartbeat',
        type: dynamodb.AttributeType.STRING,
      },
    });

    // Create Lambda layer for dependencies
    const resolverLayer = new lambda.LayerVersion(this, 'GraphQLResolverLayer', {
      layerVersionName: `multi-agent-resolver-layer-${props.environment}`,
      code: lambda.Code.fromAsset(path.join(__dirname, 'streaming-api/lambda-layer'), {
        bundling: {
          image: lambda.Runtime.NODEJS_18_X.bundlingImage,
          user: 'root',
          command: [
            'bash', '-c', [
              'cp -r /asset-input/* /asset-output/',
              'cd /asset-output',
              'npm config set cache /tmp/.npm --global',
              'npm install --production --omit=dev',
              'mkdir -p nodejs',
              'mv node_modules nodejs/',
              'rm -f package.json package-lock.json'
            ].join(' && ')
          ],
          environment: {
            NPM_CONFIG_CACHE: '/tmp/.npm',
            NPM_CONFIG_UPDATE_NOTIFIER: 'false'
          }
        },
      }),
      compatibleRuntimes: [lambda.Runtime.NODEJS_18_X, lambda.Runtime.NODEJS_LATEST],
      description: 'Dependencies for Multi-Agent GraphQL resolver function',
    });

    // Create Lambda function for GraphQL resolvers
    this.resolverFunction = new lambda.Function(this, 'GraphQLResolverFunction', {
      functionName: `multi-agent-graphql-resolver-${props.environment}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'streaming-api/resolver-function')),
      layers: [resolverLayer],
      timeout: cdk.Duration.minutes(5), // Allow up to 5 minutes for supervisor agent processing
      memorySize: 512,
      vpc: props.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      securityGroups: [props.lambdaSecurityGroup],
      environment: {
        CHAT_SESSIONS_TABLE: this.chatSessionsTable.tableName,
        CHAT_MESSAGES_TABLE: this.chatMessagesTable.tableName,
        AGENT_STATUS_TABLE: this.agentStatusTable.tableName,
        SUPERVISOR_AGENT_URL: props.supervisorAgentUrl || process.env.SUPERVISOR_AGENT_URL || 'https://supervisor-service:8000',
        ENVIRONMENT: props.environment,
        LOG_LEVEL: 'INFO',
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant DynamoDB permissions to Lambda
    this.chatSessionsTable.grantReadWriteData(this.resolverFunction);
    this.chatMessagesTable.grantReadWriteData(this.resolverFunction);
    this.agentStatusTable.grantReadWriteData(this.resolverFunction);

    // Create AppSync GraphQL API
    this.graphqlApi = new appsync.GraphqlApi(this, 'MultiAgentGraphQLApi', {
      name: `multi-agent-api-${props.environment}`,
      schema: appsync.SchemaFile.fromAsset(path.join(__dirname, 'streaming-api/schema.graphql')),
      authorizationConfig: {
        defaultAuthorization: {
          authorizationType: appsync.AuthorizationType.USER_POOL,
          userPoolConfig: {
            userPool: this.userPool,
            defaultAction: appsync.UserPoolDefaultAction.ALLOW,
          },
        },
        additionalAuthorizationModes: [
          {
            authorizationType: appsync.AuthorizationType.IAM,
          },
        ],
      },
      logConfig: {
        fieldLogLevel: appsync.FieldLogLevel.ALL,
        retention: logs.RetentionDays.ONE_WEEK,
      },
      xrayEnabled: true,
    });

    // Define authorization providers
    const iamProvider: appsync.AppSyncAuthProvider = {
      authorizationType: appsync.AppSyncAuthorizationType.IAM,
    };

    const userPoolProvider: appsync.AppSyncAuthProvider = {
      authorizationType: appsync.AppSyncAuthorizationType.USER_POOL,
      cognitoConfig: {
        userPool: this.userPool,
      }
    };

    const apiKeyProvider: appsync.AppSyncAuthProvider = {
      authorizationType: appsync.AppSyncAuthorizationType.API_KEY,
    };

    // Create AppSync Events API for real-time messaging
    this.eventsApi = new appsync.EventApi(this, 'MultiAgentEventsApi', {
      apiName: `multi-agent-events-api-${props.environment}`,
      authorizationConfig: {
        authProviders: [
          userPoolProvider,
          iamProvider,
          apiKeyProvider
        ],
      },
    });

    // Create event channels for different types of real-time communication
    this.eventsApi.addChannelNamespace('langgraph-sessions');
    this.eventsApi.addChannelNamespace('agent-status');
    this.eventsApi.addChannelNamespace('system-events');
    this.eventsApi.addChannelNamespace('supervisor');
    
    // Add new channels for Events API pub/sub implementation
    this.eventsApi.addChannelNamespace('langgraph-requests');   // Frontend → ECS
    this.eventsApi.addChannelNamespace('langgraph-responses');  // ECS → Frontend

    // Grant ECS task permission to publish to Events API
    const eventsPublishPolicy = new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'appsync:PostToConnection',
        'appsync:GetChannel',
        'appsync:ListChannels'
      ],
      resources: [
        `${this.eventsApi.apiArn}/*`,
        `${this.eventsApi.apiArn}/channels/*`
      ]
    });

    const eventsSubscribePolicy = new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'appsync:EventConnect',
        'appsync:EventSubscribe'
      ],
      resources: [
        `${this.eventsApi.apiArn}/*`,
        `${this.eventsApi.apiArn}/channels/*`
      ]
    });

    // Add policies to Lambda function for Events API access
    this.resolverFunction.addToRolePolicy(eventsPublishPolicy);
    this.resolverFunction.addToRolePolicy(eventsSubscribePolicy);

    // Update Lambda environment variables
    this.resolverFunction.addEnvironment('EVENTS_API_ID', this.eventsApi.apiId);
    this.resolverFunction.addEnvironment('EVENTS_API_ARN', this.eventsApi.apiArn);
    // this.resolverFunction.addEnvironment('EVENTS_API_ENDPOINT',
    //   `https://${this.eventsApi.apiId}.appsync-api.${cdk.Stack.of(this).region}.amazonaws.com/event`);
    this.resolverFunction.addEnvironment('EVENTS_API_ENDPOINT', this.eventsApi.realtimeDns);

    // Create Lambda data source
    const lambdaDataSource = this.graphqlApi.addLambdaDataSource(
      'LambdaDataSource',
      this.resolverFunction,
      {
        name: 'MultiAgentLambdaDataSource',
        description: 'Lambda data source for multi-agent GraphQL operations',
      }
    );

    // Create DynamoDB data sources
    const chatSessionsDataSource = this.graphqlApi.addDynamoDbDataSource(
      'ChatSessionsDataSource',
      this.chatSessionsTable,
      {
        name: 'ChatSessionsDataSource',
        description: 'DynamoDB data source for chat sessions',
      }
    );

    const chatMessagesDataSource = this.graphqlApi.addDynamoDbDataSource(
      'ChatMessagesDataSource',
      this.chatMessagesTable,
      {
        name: 'ChatMessagesDataSource',
        description: 'DynamoDB data source for chat messages',
      }
    );

    const agentStatusDataSource = this.graphqlApi.addDynamoDbDataSource(
      'AgentStatusDataSource',
      this.agentStatusTable,
      {
        name: 'AgentStatusDataSource',
        description: 'DynamoDB data source for agent status',
      }
    );

    // Create resolvers for mutations (using Lambda)
    lambdaDataSource.createResolver('SendChatResolver', {
      typeName: 'Mutation',
      fieldName: 'sendChat',
    });

    lambdaDataSource.createResolver('CreateSessionResolver', {
      typeName: 'Mutation',
      fieldName: 'createSession',
    });

    lambdaDataSource.createResolver('CloseSessionResolver', {
      typeName: 'Mutation',
      fieldName: 'closeSession',
    });

    lambdaDataSource.createResolver('ExecuteTaskResolver', {
      typeName: 'Mutation',
      fieldName: 'executeTaskOnAgent',
    });

    lambdaDataSource.createResolver('AggregateDataResolver', {
      typeName: 'Mutation',
      fieldName: 'aggregateDataFromAgents',
    });

    lambdaDataSource.createResolver('UpdateAgentStatusResolver', {
      typeName: 'Mutation',
      fieldName: 'updateAgentStatus',
    });

    // Create resolvers for queries (mix of Lambda and direct DynamoDB)
    lambdaDataSource.createResolver('HealthCheckResolver', {
      typeName: 'Query',
      fieldName: 'healthCheck',
    });

    // Direct DynamoDB resolvers for simple queries
    chatSessionsDataSource.createResolver('GetSessionResolver', {
      typeName: 'Query',
      fieldName: 'getSession',
      requestMappingTemplate: appsync.MappingTemplate.dynamoDbGetItem('sessionId', 'sessionId'),
      responseMappingTemplate: appsync.MappingTemplate.dynamoDbResultItem(),
    });

    agentStatusDataSource.createResolver('GetAgentStatusResolver', {
      typeName: 'Query',
      fieldName: 'getAgentStatus',
      requestMappingTemplate: appsync.MappingTemplate.dynamoDbGetItem('agentId', 'agentId'),
      responseMappingTemplate: appsync.MappingTemplate.dynamoDbResultItem(),
    });

    // Complex queries using Lambda
    lambdaDataSource.createResolver('GetUserSessionsResolver', {
      typeName: 'Query',
      fieldName: 'getUserSessions',
    });

    lambdaDataSource.createResolver('GetChatHistoryResolver', {
      typeName: 'Query',
      fieldName: 'getChatHistory',
    });

    lambdaDataSource.createResolver('GetAllAgentStatusesResolver', {
      typeName: 'Query',
      fieldName: 'getAllAgentStatuses',
    });

    lambdaDataSource.createResolver('GetAgentsByTypeResolver', {
      typeName: 'Query',
      fieldName: 'getAgentsByType',
    });

    lambdaDataSource.createResolver('GetTaskResultResolver', {
      typeName: 'Query',
      fieldName: 'getTaskResult',
    });

    lambdaDataSource.createResolver('GetUserTasksResolver', {
      typeName: 'Query',
      fieldName: 'getUserTasks',
    });

    // Grant AppSync permission to invoke Lambda
    this.resolverFunction.addPermission('AppSyncInvokePermission', {
      principal: new iam.ServicePrincipal('appsync.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: this.graphqlApi.arn,
    });

    // Output important values
    new cdk.CfnOutput(this, 'GraphQLApiUrl', {
      value: this.graphqlApi.graphqlUrl,
      description: 'GraphQL API URL',
      exportName: `${props.environment}-GraphQLApiUrl`,
    });

    new cdk.CfnOutput(this, 'GraphQLApiId', {
      value: this.graphqlApi.apiId,
      description: 'GraphQL API ID',
      exportName: `${props.environment}-GraphQLApiId`,
    });

    new cdk.CfnOutput(this, 'UserPoolId', {
      value: this.userPool.userPoolId,
      description: 'Cognito User Pool ID',
      exportName: `${props.environment}-UserPoolId`,
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: this.userPoolClient.userPoolClientId,
      description: 'Cognito User Pool Client ID',
      exportName: `${props.environment}-UserPoolClientId`,
    });

    // DynamoDB Table Outputs
    new cdk.CfnOutput(this, 'ChatSessionsTableName', {
      value: this.chatSessionsTable.tableName,
      description: 'Chat Sessions DynamoDB Table Name',
      exportName: `${props.environment}-ChatSessionsTableName`,
    });

    new cdk.CfnOutput(this, 'ChatMessagesTableName', {
      value: this.chatMessagesTable.tableName,
      description: 'Chat Messages DynamoDB Table Name',
      exportName: `${props.environment}-ChatMessagesTableName`,
    });

    new cdk.CfnOutput(this, 'AgentStatusTableName', {
      value: this.agentStatusTable.tableName,
      description: 'Agent Status DynamoDB Table Name',
      exportName: `${props.environment}-AgentStatusTableName`,
    });

    new cdk.CfnOutput(this, 'ChatSessionsTableArn', {
      value: this.chatSessionsTable.tableArn,
      description: 'Chat Sessions DynamoDB Table ARN',
      exportName: `${props.environment}-ChatSessionsTableArn`,
    });

    new cdk.CfnOutput(this, 'ChatMessagesTableArn', {
      value: this.chatMessagesTable.tableArn,
      description: 'Chat Messages DynamoDB Table ARN',
      exportName: `${props.environment}-ChatMessagesTableArn`,
    });

    new cdk.CfnOutput(this, 'AgentStatusTableArn', {
      value: this.agentStatusTable.tableArn,
      description: 'Agent Status DynamoDB Table ARN',
      exportName: `${props.environment}-AgentStatusTableArn`,
    });

    new cdk.CfnOutput(this, 'CheckpointsTableName', {
      value: this.checkpointsTable.tableName,
      description: 'LangGraph Checkpoints DynamoDB Table Name',
      exportName: `${props.environment}-CheckpointsTableName`,
    });

    new cdk.CfnOutput(this, 'CheckpointsTableArn', {
      value: this.checkpointsTable.tableArn,
      description: 'LangGraph Checkpoints DynamoDB Table ARN',
      exportName: `${props.environment}-CheckpointsTableArn`,
    });

    // Add Events API outputs
    new cdk.CfnOutput(this, 'EventsApiId', {
      value: this.eventsApi.apiId,
      description: 'AppSync Events API ID',
      exportName: `${props.environment}-EventsApiId`,
    });

    new cdk.CfnOutput(this, 'EventsApiArn', {
      value: this.eventsApi.apiArn,
      description: 'AppSync Events API ARN',
      exportName: `${props.environment}-EventsApiArn`,
    });

    // new cdk.CfnOutput(this, 'EventsApiEndpoint', {
    //   value: `https://${this.eventsApi.apiId}.appsync-api.${cdk.Stack.of(this).region}.amazonaws.com/event`,
    //   description: 'AppSync Events API Endpoint',
    //   exportName: `${props.environment}-EventsApiEndpoint`,
    // });

    new cdk.CfnOutput(this, 'EventsApiEndpoint', {
      value: this.eventsApi.realtimeDns,
      description: 'AppSync Events API Endpoint',
      exportName: `${props.environment}-EventsApiEndpoint`,
    });

    new cdk.CfnOutput(this, 'EventsApiKey', {
      value: Object.keys(this.eventsApi.apiKeys)[0] ? this.eventsApi.apiKeys[Object.keys(this.eventsApi.apiKeys)[0]].attrApiKey : 'No API key available',
      description: 'AppSync Events API Key',
      exportName: `${props.environment}-EventsApiKey`,
    });

    new cdk.CfnOutput(this, 'EventsApiHttpDomain', {
      value: this.eventsApi.httpDns,
      description: 'AppSync Events API Http Domain',
      exportName: `${props.environment}-EventsApiHttpDomain`,
    });
    // Add tags
    cdk.Tags.of(this).add('Component', 'StreamingAPI');
    cdk.Tags.of(this).add('Environment', props.environment);
  }
}