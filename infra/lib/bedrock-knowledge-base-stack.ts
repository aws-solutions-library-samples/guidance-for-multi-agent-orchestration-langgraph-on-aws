import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

export interface BedrockKnowledgeBaseStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  environment: string;
}

export class BedrockKnowledgeBaseStack extends cdk.Stack {
  public readonly knowledgeBase: bedrock.CfnKnowledgeBase;
  public readonly dataSource: bedrock.CfnDataSource;
  public readonly unstructuredDataBucket: s3.Bucket;
  public readonly opensearchCollection: opensearchserverless.CfnCollection;

  constructor(scope: Construct, id: string, props: BedrockKnowledgeBaseStackProps) {
    super(scope, id, props);

    const { vpc, environment } = props;

    // KMS Key for encryption
    const kmsKey = new kms.Key(this, 'BedrockKBKey', {
      description: 'KMS key for Bedrock Knowledge Base encryption',
      enableKeyRotation: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Change to RETAIN for production
    });

    // S3 Bucket for unstructured data
    this.unstructuredDataBucket = new s3.Bucket(this, 'UnstructuredDataBucket', {
      bucketName: `multiagent-unstructured-data-${environment}-${this.account}`,
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: kmsKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
        {
          id: 'DeleteIncompleteMultipartUploads',
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
        },
      ],
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Change to RETAIN for production
    });

    // Collection name for OpenSearch Serverless (must be lowercase and follow naming rules)
    const collectionName = `bedrock-kb-${environment}`.toLowerCase();
    const indexName = 'bedrock-knowledge-base-default-index';

    // Bedrock service role - Create this first as it's needed for data access policy
    const bedrockServiceRole = new iam.Role(this, 'BedrockServiceRole', {
      roleName: `BedrockKB-${environment}-${this.region}`,
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Service role for Bedrock Knowledge Base - OpenSearch Serverless',
      inlinePolicies: {
        BedrockKnowledgeBasePolicy: new iam.PolicyDocument({
          statements: [
            // OpenSearch Serverless permissions - Fixed format
            new iam.PolicyStatement({
              sid: 'OpenSearchServerlessAPIAccessAllStatement',
              effect: iam.Effect.ALLOW,
              actions: [
                'aoss:APIAccessAll',
              ],
              resources: [
                `arn:aws:aoss:${this.region}:${this.account}:collection/*`,
              ],
            }),
            // S3 permissions for data source
            new iam.PolicyStatement({
              sid: 'S3DataSourceAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                's3:GetObject',
                's3:ListBucket',
                's3:GetBucketLocation',
              ],
              resources: [
                this.unstructuredDataBucket.bucketArn,
                `${this.unstructuredDataBucket.bucketArn}/*`,
              ],
            }),
            // Bedrock model invocation
            new iam.PolicyStatement({
              sid: 'BedrockModelAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:InvokeModelWithResponseStream',
              ],
              resources: [
                `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
                `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0`,
              ],
            }),
            // KMS permissions
            new iam.PolicyStatement({
              sid: 'KMSAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'kms:Decrypt',
                'kms:GenerateDataKey',
              ],
              resources: [kmsKey.keyArn],
            }),
          ],
        }),
      },
    });

    // Store KB role ARN in SSM for reference (following AWS sample pattern)
    const kbRoleArnParam = new ssm.StringParameter(this, 'KbRoleArnParam', {
      parameterName: `/multiagent/${environment}/kbRoleArn`,
      stringValue: bedrockServiceRole.roleArn,
      description: 'Bedrock Knowledge Base service role ARN',
    });

    // OpenSearch Serverless Encryption Policy
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'EncryptionPolicy', {
      name: `${collectionName}-enc`,
      type: 'encryption',
      description: 'Encryption policy for Bedrock Knowledge Base collection',
      policy: JSON.stringify({
        Rules: [
          {
            ResourceType: 'collection',
            Resource: [`collection/${collectionName}`],
          },
        ],
        AWSOwnedKey: true,
      }),
    });

    // OpenSearch Serverless Network Policy - Allow public access for CloudFormation
    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'NetworkPolicy', {
      name: `${collectionName}-net`,
      type: 'network',
      description: 'Network policy for Bedrock Knowledge Base collection',
      policy: JSON.stringify([
        {
          Description: `Public access for ${collectionName} collection`,
          Rules: [
            {
              ResourceType: 'collection',
              Resource: [`collection/${collectionName}`],
            },
            {
              ResourceType: 'dashboard',
              Resource: [`collection/${collectionName}`],
            },
          ],
          // SourceServices: ['bedrock.amazonaws.com'],
          AllowFromPublic: true, // Changed to true for CloudFormation CfnIndex to work
        },
      ]),
    });

    // Add dependency: network policy after encryption policy
    networkPolicy.node.addDependency(encryptionPolicy);

    // OpenSearch Serverless Collection
    this.opensearchCollection = new opensearchserverless.CfnCollection(this, 'OpenSearchCollection', {
      name: collectionName,
      description: `${collectionName}-multiagent-collection`,
      type: 'VECTORSEARCH',
      standbyReplicas: 'DISABLED', // For cost optimization in development
      tags: [
        {
          key: 'Environment',
          value: environment,
        },
        {
          key: 'Project',
          value: 'MultiAgentSystem',
        },
        {
          key: 'Component',
          value: 'BedrockKnowledgeBase',
        },
      ],
    });

    // Collection depends on network policy
    this.opensearchCollection.node.addDependency(networkPolicy);

    // Store collection ARN in SSM (following AWS sample pattern)
    const collectionArnParam = new ssm.StringParameter(this, 'CollectionArnParam', {
      parameterName: `/multiagent/${environment}/collectionArn`,
      stringValue: this.opensearchCollection.attrArn,
      description: 'OpenSearch Serverless collection ARN',
    });

    // OpenSearch Serverless Data Access Policy - Created AFTER collection
    const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'DataAccessPolicy', {
      name: `${collectionName}-access`,
      type: 'data',
      description: 'Data access policy for Bedrock Knowledge Base collection',
      policy: JSON.stringify([
        {
          Rules: [
            {
              Resource: [`collection/${collectionName}`],
              Permission: [
                'aoss:CreateCollectionItems',
                'aoss:DeleteCollectionItems',
                'aoss:UpdateCollectionItems',
                'aoss:DescribeCollectionItems',
                'aoss:*',
              ],
              ResourceType: 'collection',
            },
            {
              Resource: [`index/${collectionName}/*`],
              Permission: [
                'aoss:ReadDocument',
                'aoss:WriteDocument',
                'aoss:CreateIndex',
                'aoss:DeleteIndex',
                'aoss:UpdateIndex',
                'aoss:DescribeIndex',
                'aoss:*',
              ],
              ResourceType: 'index',
            },
          ],
          Principal: [
            bedrockServiceRole.roleArn,
            `arn:aws:iam::${this.account}:root`, // Root account access (includes CloudFormation)
          ],
        },
      ]),
    });

    // Data access policy depends on collection
    dataAccessPolicy.node.addDependency(this.opensearchCollection);

    // Add wait condition to ensure collection is active (following AWS sample pattern)
    const waitCondition = new cdk.custom_resources.AwsCustomResource(this, 'WaitForCollection', {
      onCreate: {
        service: 'OpenSearchServerless',
        action: 'listCollections',
        parameters: {},
        physicalResourceId: cdk.custom_resources.PhysicalResourceId.of('WaitForCollection'),
      },
      policy: cdk.custom_resources.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cdk.custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
      timeout: cdk.Duration.minutes(5),
    });

    waitCondition.node.addDependency(this.opensearchCollection);
    waitCondition.node.addDependency(dataAccessPolicy);

    // Create OpenSearch Index using native CfnIndex (following AWS sample pattern)
    const ossIndex = new opensearchserverless.CfnIndex(this, 'OSSCfnIndex', {
      collectionEndpoint: this.opensearchCollection.attrCollectionEndpoint,
      indexName: indexName,
      mappings: {
        properties: {
          'bedrock-knowledge-base-default-vector': {
            type: 'knn_vector',
            dimension: 1024,
            method: {
              engine: 'faiss',
              name: 'hnsw',
              parameters: {
                efConstruction: 512,
                m: 16,
              },
              spaceType: 'l2',
            },
          },
          'AMAZON_BEDROCK_METADATA': {
            type: 'text',
            index: true,
          },
          'AMAZON_BEDROCK_TEXT_CHUNK': {
            type: 'text',
            index: true,
          },
        },
      },
      settings: {
        index: {
          knn: true,
          knnAlgoParamEfSearch: 512,
        },
      },
    });

    ossIndex.node.addDependency(dataAccessPolicy);
    ossIndex.node.addDependency(this.opensearchCollection);
    ossIndex.node.addDependency(waitCondition);

    // Wait for index to be queryable by Bedrock
    const waitForIndex = new cdk.custom_resources.AwsCustomResource(this, 'WaitForIndex', {
      onCreate: {
        service: 'OpenSearchServerless',
        action: 'batchGetCollection',
        parameters: {
          names: [collectionName]
        },
        physicalResourceId: cdk.custom_resources.PhysicalResourceId.of('WaitForIndex'),
      },
      policy: cdk.custom_resources.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cdk.custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
      timeout: cdk.Duration.minutes(10),
    });

    waitForIndex.node.addDependency(ossIndex);

    // Knowledge Base - Created after index is ready
    this.knowledgeBase = new bedrock.CfnKnowledgeBase(this, 'UnstructuredKnowledgeBase', {
      name: `UnstructuredDataKB-${environment}`,
      description: 'Knowledge base for document retrieval and RAG applications using OpenSearch Serverless',
      roleArn: bedrockServiceRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
          embeddingModelConfiguration: {
            bedrockEmbeddingModelConfiguration: {
              dimensions: 1024,
              embeddingDataType: 'FLOAT32',
            },
          },
        },
      },
      storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
          collectionArn: this.opensearchCollection.attrArn,
          vectorIndexName: indexName,
          fieldMapping: {
            vectorField: 'bedrock-knowledge-base-default-vector',
            textField: 'AMAZON_BEDROCK_TEXT_CHUNK',
            metadataField: 'AMAZON_BEDROCK_METADATA',
          },
        },
      },
      tags: {
        Environment: environment,
        Project: 'MultiAgentSystem',
        Component: 'BedrockKnowledgeBase',
      },
    });

    // Knowledge base depends directly on index wait condition
    this.knowledgeBase.node.addDependency(waitForIndex);

    // Data Source
    this.dataSource = new bedrock.CfnDataSource(this, 'UnstructuredDataSource', {
      knowledgeBaseId: this.knowledgeBase.attrKnowledgeBaseId,
      name: `S3DataSource-${environment}`,
      description: 'S3 data source for documents and unstructured content',
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: this.unstructuredDataBucket.bucketArn,
          // inclusionPrefixes: ['documents/', 'pdfs/', 'text/', 'images/'],
          bucketOwnerAccountId: this.account,
        },
      },
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          chunkingStrategy: 'FIXED_SIZE',
          fixedSizeChunkingConfiguration: {
            maxTokens: 1000,
            overlapPercentage: 20,
          },
        },
        parsingConfiguration: {
          parsingStrategy: 'BEDROCK_FOUNDATION_MODEL',
          bedrockFoundationModelConfiguration: {
            modelArn: `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0`,
            parsingPrompt: {
              parsingPromptText: 'Extract and structure the key information from this document, preserving important context and relationships.',
            },
          },
        },
      },
    });

    // CloudWatch Log Group for monitoring
    const logGroup = new cdk.aws_logs.LogGroup(this, 'BedrockKBLogGroup', {
      logGroupName: `/aws/bedrock/knowledgebase/${environment}`,
      retention: cdk.aws_logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Outputs
    new cdk.CfnOutput(this, 'KnowledgeBaseId', {
      value: this.knowledgeBase.attrKnowledgeBaseId,
      description: 'Bedrock Knowledge Base ID',
      exportName: `${this.stackName}-KnowledgeBaseId`,
    });

    new cdk.CfnOutput(this, 'DataSourceId', {
      value: this.dataSource.attrDataSourceId,
      description: 'Bedrock Data Source ID',
      exportName: `${this.stackName}-DataSourceId`,
    });

    new cdk.CfnOutput(this, 'S3BucketName', {
      value: this.unstructuredDataBucket.bucketName,
      description: 'S3 bucket for unstructured data',
      exportName: `${this.stackName}-S3BucketName`,
    });

    new cdk.CfnOutput(this, 'OpenSearchCollectionEndpoint', {
      value: this.opensearchCollection.attrCollectionEndpoint,
      description: 'OpenSearch Serverless collection endpoint',
      exportName: `${this.stackName}-OpenSearchEndpoint`,
    });

    new cdk.CfnOutput(this, 'OpenSearchCollectionArn', {
      value: this.opensearchCollection.attrArn,
      description: 'OpenSearch Serverless collection ARN',
      exportName: `${this.stackName}-OpenSearchArn`,
    });

    new cdk.CfnOutput(this, 'BedrockServiceRoleArn', {
      value: bedrockServiceRole.roleArn,
      description: 'Bedrock service role ARN',
      exportName: `${this.stackName}-BedrockServiceRoleArn`,
    });
  }
}
