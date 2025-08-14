import {
  CfnOutput,
  Fn,
  RemovalPolicy,
  aws_cloudfront as cloudfront,
  aws_cloudfront_origins as cloudfront_origins,
  aws_codebuild as codebuild,
  custom_resources,
  CustomResource,
  Duration,
  aws_iam as iam,
  aws_lambda,
  aws_logs as logs,
  aws_s3 as s3,
  aws_s3_assets as s3_assets,
  Stack,
  StackProps,
  aws_stepfunctions as stepfunctions,
  aws_wafv2 as wafv2,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as path from "path";

export interface FrontendStackProps extends StackProps {
  environment: string;
  streamingApiStackName: string;
}

export class FrontendStack extends Stack {
  public readonly websiteBucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;
  public readonly urls: string[];

  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    // Get StreamingAPI stack outputs for environment variables
    const graphqlApiUrl = Fn.importValue(`${props.environment}-GraphQLApiUrl`);
    const userPoolId = Fn.importValue(`${props.environment}-UserPoolId`);
    const userPoolClientId = Fn.importValue(`${props.environment}-UserPoolClientId`);

    // Create logging bucket for CloudFront and S3 access logs
    const loggingBucket = new s3.Bucket(this, "LoggingBucket", {
      bucketName: `multiagent-frontend-logs-${props.environment}-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_PREFERRED, // Enable ACL access for CloudFront logging
      removalPolicy: props.environment === 'prod'
        ? RemovalPolicy.RETAIN
        : RemovalPolicy.DESTROY,
      autoDeleteObjects: props.environment !== 'prod',
    });

    // S3 bucket configuration for hosting static files
    this.websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      bucketName: `multiagent-frontend-${props.environment}-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      serverAccessLogsBucket: loggingBucket,
      serverAccessLogsPrefix: 'website-access-logs/',
      removalPolicy: props.environment === 'prod'
        ? RemovalPolicy.RETAIN
        : RemovalPolicy.DESTROY,
      autoDeleteObjects: props.environment !== 'prod',
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          enabled: true,
          noncurrentVersionExpiration: Duration.days(30),
          abortIncompleteMultipartUploadAfter: Duration.days(7),
        },
      ],
    });

    // Create CloudFront Web ACL for security
    const cloudfrontWebAcl = new wafv2.CfnWebACL(this, "CloudfrontWebAcl", {
      scope: "CLOUDFRONT",
      defaultAction: { allow: {} },
      rules: [
        {
          name: "AWSManagedRulesCommonRuleSet",
          priority: 1,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: "AWS",
              name: "AWSManagedRulesCommonRuleSet",
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: "CommonRuleSetMetric",
          },
        },
        {
          name: "AWSManagedRulesAmazonIpReputationList",
          priority: 2,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: "AWS",
              name: "AWSManagedRulesAmazonIpReputationList",
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: "IpReputationListMetric",
          },
        },
        {
          name: "AWSManagedRulesBotControlRuleSet",
          priority: 3,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: "AWS",
              name: "AWSManagedRulesBotControlRuleSet",
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: "BotControlRuleSetMetric",
          },
        },
      ],
      visibilityConfig: {
        sampledRequestsEnabled: true,
        cloudWatchMetricsEnabled: true,
        metricName: "webACL",
      },
    });

    // CloudFront distribution configuration
    this.distribution = new cloudfront.Distribution(this, "Distribution", {
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: cloudfront_origins.S3BucketOrigin.withOriginAccessControl(this.websiteBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        originRequestPolicy: cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
      },
      errorResponses: [
        {
          httpStatus: 404,
          responsePagePath: "/index.html",
          responseHttpStatus: 200,
        },
        {
          httpStatus: 403,
          responsePagePath: "/index.html",
          responseHttpStatus: 200,
        },
      ],
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
      sslSupportMethod: cloudfront.SSLMethod.SNI,
      webAclId: cloudfrontWebAcl.attrArn,
      logBucket: loggingBucket,
      logIncludesCookies: true,
      logFilePrefix: "distribution",
    });

    this.urls = [
      `https://${this.distribution.distributionDomainName}`,
      "http://localhost:3000",
    ];

    // Outputs for verification and integration
    new CfnOutput(this, 'FrontendBucketName', {
      value: this.websiteBucket.bucketName,
      description: 'S3 bucket name for frontend hosting',
      exportName: `${this.stackName}-BucketName`,
    });

    new CfnOutput(this, 'FrontendDistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront distribution ID for frontend',
      exportName: `${this.stackName}-DistributionId`,
    });

    new CfnOutput(this, 'FrontendDistributionDomainName', {
      value: this.distribution.distributionDomainName,
      description: 'CloudFront distribution domain name for frontend',
      exportName: `${this.stackName}-DistributionDomainName`,
    });

    new CfnOutput(this, 'FrontendUrl', {
      value: `https://${this.distribution.distributionDomainName}`,
      description: 'Frontend application URL',
      exportName: `${this.stackName}-Url`,
    });

    // Create deployment resources directly in this stack
    const environmentVariables = {
      VITE_AWS_REGION: this.region,
      VITE_GRAPHQL_API_URL: graphqlApiUrl.toString(),
      VITE_USER_POOL_ID: userPoolId.toString(),
      VITE_USER_POOL_CLIENT_ID: userPoolClientId.toString(),
      VITE_APP_TITLE: 'Multi-Agent Customer Support',
      VITE_APP_VERSION: '1.0.0',
      NODE_ENV: props.environment === 'prod' ? 'production' : 'development',
    };

    const websiteAssets = new s3_assets.Asset(this, "WebsiteAssets", {
      path: path.join(__dirname, "..", "..", "frontend"),
      exclude: ["node_modules", "dist"],
    });

    const buildEnvironmentVariables: codebuild.BuildEnvironment["environmentVariables"] =
      Object.fromEntries(
        Object.entries(environmentVariables).map(([key, value]) => [
          key,
          { value },
        ])
      );

    const reactProject = new codebuild.Project(this, "ReactProject", {
      source: codebuild.Source.s3({
        bucket: websiteAssets.bucket,
        path: websiteAssets.s3ObjectKey,
      }),
      artifacts: codebuild.Artifacts.s3({
        bucket: this.websiteBucket,
        includeBuildId: false,
        packageZip: false,
        name: "/",
        encryption: true, // Enable S3 encryption for artifacts
      }),
      environment: {
        buildImage: codebuild.LinuxArmBuildImage.AMAZON_LINUX_2_STANDARD_3_0,
        computeType: codebuild.ComputeType.SMALL,
        privileged: false, // Disable elevated privileges for security
        environmentVariables: {
          ...buildEnvironmentVariables,
          DISTRIBUTION_ID: {
            value: this.distribution.distributionId,
          },
        },
      },
      // Enable CloudWatch logs with encryption
      logging: {
        cloudWatch: {
          logGroup: new logs.LogGroup(this, 'CodeBuildLogGroup', {
            logGroupName: `/aws/codebuild/react-build-${props.environment}`,
            retention: logs.RetentionDays.ONE_MONTH,
            removalPolicy: RemovalPolicy.DESTROY,
          }),
        },
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: "0.2",
        phases: {
          install: {
            "runtime-versions": {
              nodejs: "22",
            },
            commands: ["npm install"],
          },
          build: {
            commands: ["npm run build"],
          },
          post_build: {
            commands: [
              'aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"',
            ],
          },
        },
        artifacts: {
          files: ["**/*"],
          "base-directory": "dist",
        },
      }),
    });

    reactProject.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["cloudfront:CreateInvalidation"],
        resources: [this.distribution.distributionArn],
      })
    );

    const providerFunctionDir = path.join(__dirname, "frontend-build-trigger");

    const reactProvider = new custom_resources.Provider(this, "ReactProvider", {
      onEventHandler: new aws_lambda.Function(this, "ReactOnEventHandler", {
        runtime: aws_lambda.Runtime.NODEJS_22_X,
        handler: "index.onEventHandler",
        code: aws_lambda.Code.fromAsset(providerFunctionDir),
        timeout: Duration.minutes(15),
        initialPolicy: [
          new iam.PolicyStatement({
            actions: ["codebuild:StartBuild"],
            resources: [reactProject.projectArn],
          }),
        ],
      }),
      isCompleteHandler: new aws_lambda.Function(this, "ReactIsCompleteHandler", {
        runtime: aws_lambda.Runtime.NODEJS_22_X,
        handler: "index.isCompleteHandler",
        code: aws_lambda.Code.fromAsset(providerFunctionDir),
        timeout: Duration.minutes(1),
        initialPolicy: [
          new iam.PolicyStatement({
            actions: ["codebuild:BatchGetBuilds"],
            resources: [reactProject.projectArn],
          }),
        ],
      }),
      logRetention: logs.RetentionDays.THREE_MONTHS,
      queryInterval: Duration.seconds(15),
      totalTimeout: Duration.minutes(15),
      waiterStateMachineLogOptions: {
        level: stepfunctions.LogLevel.ALL,
      },
    });

    new CustomResource(this, "ReactCustomResource", {
      serviceToken: reactProvider.serviceToken,
      properties: {
        projectName: reactProject.projectName,
        assetHash: websiteAssets.assetHash,
      },
    });

    // Output environment variables for debugging
    const outputPrefix = this.stackName;
    Object.entries(environmentVariables).forEach(([key, value]) => {
      const outputKey = key.toLowerCase();
      const outputId = outputKey.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      const outputSuffix = outputKey.replace(/_/g, "-");

      // Add "vite-" prefix to export name if the key starts with VITE_
      const exportName = key.startsWith("VITE_")
        ? `${outputPrefix}-vite-${outputSuffix}`
        : `${outputPrefix}-${outputSuffix}`;

      new CfnOutput(this, outputId, {
        value: value,
        exportName: exportName,
      });
    });
  }
}
