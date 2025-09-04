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
  public readonly personalizationKnowledgeBase: bedrock.CfnKnowledgeBase;
  public readonly troubleshootingKnowledgeBase: bedrock.CfnKnowledgeBase;
  public readonly personalizationDataSource: bedrock.CfnDataSource;
  public readonly troubleshootingDataSource: bedrock.CfnDataSource;
  public readonly personalizationDataBucket: s3.Bucket;
  public readonly troubleshootingDataBucket: s3.Bucket;
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

    // S3 Bucket for personalization data (browsing history, customer behavior)
    this.personalizationDataBucket = new s3.Bucket(this, 'PersonalizationDataBucket', {
      bucketName: `multiagent-personalization-data-${environment}-${this.account}`,
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

    // S3 Bucket for troubleshooting data (FAQs, troubleshooting guides)
    this.troubleshootingDataBucket = new s3.Bucket(this, 'TroubleshootingDataBucket', {
      bucketName: `multiagent-troubleshooting-data-${environment}-${this.account}`,
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
    const personalizationIndexName = 'personalization-knowledge-base-index';
    const troubleshootingIndexName = 'troubleshooting-knowledge-base-index';

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
                // We won't be able to scope down the permission to the collection resource as
                // the data-access policy requires this roleArn, but the policy needs to be
                // created before creating the collection itself.
                `arn:aws:aoss:${this.region}:${this.account}:collection/*`,
              ],
            }),
            // S3 permissions for data sources
            new iam.PolicyStatement({
              sid: 'S3DataSourceAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                's3:GetObject',
                's3:ListBucket',
                's3:GetBucketLocation',
              ],
              resources: [
                this.personalizationDataBucket.bucketArn,
                `${this.personalizationDataBucket.bucketArn}/*`,
                this.troubleshootingDataBucket.bucketArn,
                `${this.troubleshootingDataBucket.bucketArn}/*`,
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

    // Create OpenSearch Index for Personalization Knowledge Base
    const personalizationIndex = new opensearchserverless.CfnIndex(this, 'PersonalizationOSSIndex', {
      collectionEndpoint: this.opensearchCollection.attrCollectionEndpoint,
      indexName: personalizationIndexName,
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

    personalizationIndex.node.addDependency(dataAccessPolicy);
    personalizationIndex.node.addDependency(this.opensearchCollection);
    personalizationIndex.node.addDependency(waitCondition);

    // Create OpenSearch Index for Troubleshooting Knowledge Base
    const troubleshootingIndex = new opensearchserverless.CfnIndex(this, 'TroubleshootingOSSIndex', {
      collectionEndpoint: this.opensearchCollection.attrCollectionEndpoint,
      indexName: troubleshootingIndexName,
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

    troubleshootingIndex.node.addDependency(dataAccessPolicy);
    troubleshootingIndex.node.addDependency(this.opensearchCollection);
    troubleshootingIndex.node.addDependency(waitCondition);

    // Wait for indexes to be queryable by Bedrock
    const waitForIndexes = new cdk.custom_resources.AwsCustomResource(this, 'WaitForIndexes', {
      onCreate: {
        service: 'OpenSearchServerless',
        action: 'batchGetCollection',
        parameters: {
          names: [collectionName]
        },
        physicalResourceId: cdk.custom_resources.PhysicalResourceId.of('WaitForIndexes'),
      },
      policy: cdk.custom_resources.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cdk.custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
      timeout: cdk.Duration.minutes(10),
    });

    waitForIndexes.node.addDependency(personalizationIndex);
    waitForIndexes.node.addDependency(troubleshootingIndex);

    // Personalization Knowledge Base - Created after indexes are ready
    this.personalizationKnowledgeBase = new bedrock.CfnKnowledgeBase(this, 'PersonalizationKnowledgeBase', {
      name: `PersonalizationKB-${environment}`,
      description: 'Knowledge base for customer browsing history and personalization data',
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
          vectorIndexName: personalizationIndexName,
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
        Component: 'PersonalizationKnowledgeBase',
      },
    });

    // Troubleshooting Knowledge Base - Created after indexes are ready
    this.troubleshootingKnowledgeBase = new bedrock.CfnKnowledgeBase(this, 'TroubleshootingKnowledgeBase', {
      name: `TroubleshootingKB-${environment}`,
      description: 'Knowledge base for FAQs and troubleshooting guides',
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
          vectorIndexName: troubleshootingIndexName,
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
        Component: 'TroubleshootingKnowledgeBase',
      },
    });

    // Knowledge bases depend directly on indexes wait condition
    this.personalizationKnowledgeBase.node.addDependency(waitForIndexes);
    this.troubleshootingKnowledgeBase.node.addDependency(waitForIndexes);

    // Personalization Data Source
    this.personalizationDataSource = new bedrock.CfnDataSource(this, 'PersonalizationDataSource', {
      knowledgeBaseId: this.personalizationKnowledgeBase.attrKnowledgeBaseId,
      name: `PersonalizationS3DataSource-${environment}`,
      description: 'S3 data source for customer browsing history and personalization data',
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: this.personalizationDataBucket.bucketArn,
          inclusionPrefixes: ['browsing-history/'],
          bucketOwnerAccountId: this.account,
        },
      },
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          chunkingStrategy: 'FIXED_SIZE',
          fixedSizeChunkingConfiguration: {
            maxTokens: 800,
            overlapPercentage: 15,
          },
        },
        parsingConfiguration: {
          parsingStrategy: 'BEDROCK_FOUNDATION_MODEL',
          bedrockFoundationModelConfiguration: {
            modelArn: `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0`,
            parsingPrompt: {
              parsingPromptText: 'Extract customer behavior patterns, browsing history, and personalization insights from this data, preserving customer context and preferences.',
            },
          },
        },
      },
    });

    // Troubleshooting Data Source
    this.troubleshootingDataSource = new bedrock.CfnDataSource(this, 'TroubleshootingDataSource', {
      knowledgeBaseId: this.troubleshootingKnowledgeBase.attrKnowledgeBaseId,
      name: `TroubleshootingS3DataSource-${environment}`,
      description: 'S3 data source for FAQs and troubleshooting guides',
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: this.troubleshootingDataBucket.bucketArn,
          inclusionPrefixes: ['faqs/'],
          bucketOwnerAccountId: this.account,
        },
      },
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          chunkingStrategy: 'FIXED_SIZE',
          fixedSizeChunkingConfiguration: {
            maxTokens: 1200,
            overlapPercentage: 25,
          },
        },
        parsingConfiguration: {
          parsingStrategy: 'BEDROCK_FOUNDATION_MODEL',
          bedrockFoundationModelConfiguration: {
            modelArn: `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0`,
            parsingPrompt: {
              parsingPromptText: 'Extract troubleshooting steps, FAQ answers, and support information from this document, preserving step-by-step instructions and product-specific details.',
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
    new cdk.CfnOutput(this, 'PersonalizationKnowledgeBaseId', {
      value: this.personalizationKnowledgeBase.attrKnowledgeBaseId,
      description: 'Personalization Bedrock Knowledge Base ID',
      exportName: `${this.stackName}-PersonalizationKnowledgeBaseId`,
    });

    new cdk.CfnOutput(this, 'TroubleshootingKnowledgeBaseId', {
      value: this.troubleshootingKnowledgeBase.attrKnowledgeBaseId,
      description: 'Troubleshooting Bedrock Knowledge Base ID',
      exportName: `${this.stackName}-TroubleshootingKnowledgeBaseId`,
    });

    new cdk.CfnOutput(this, 'PersonalizationDataSourceId', {
      value: this.personalizationDataSource.attrDataSourceId,
      description: 'Personalization Bedrock Data Source ID',
      exportName: `${this.stackName}-PersonalizationDataSourceId`,
    });

    new cdk.CfnOutput(this, 'TroubleshootingDataSourceId', {
      value: this.troubleshootingDataSource.attrDataSourceId,
      description: 'Troubleshooting Bedrock Data Source ID',
      exportName: `${this.stackName}-TroubleshootingDataSourceId`,
    });

    new cdk.CfnOutput(this, 'PersonalizationS3BucketName', {
      value: this.personalizationDataBucket.bucketName,
      description: 'S3 bucket for personalization data',
      exportName: `${this.stackName}-PersonalizationS3BucketName`,
    });

    new cdk.CfnOutput(this, 'TroubleshootingS3BucketName', {
      value: this.troubleshootingDataBucket.bucketName,
      description: 'S3 bucket for troubleshooting data',
      exportName: `${this.stackName}-TroubleshootingS3BucketName`,
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
