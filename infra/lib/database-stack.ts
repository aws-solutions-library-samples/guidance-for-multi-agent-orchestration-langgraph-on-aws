import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export interface DatabaseStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  databaseSecurityGroup: ec2.SecurityGroup;
}

export class DatabaseStack extends cdk.Stack {
  public readonly database: rds.DatabaseCluster;
  public readonly databaseSecret: secretsmanager.Secret;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    const { vpc, databaseSecurityGroup } = props;

    // Create database credentials secret
    this.databaseSecret = new secretsmanager.Secret(this, 'DatabaseSecret', {
      description: 'Database credentials for multi-agent system',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: 'postgres' }),
        generateStringKey: 'password',
        excludeCharacters: '"@/\\\'',
        passwordLength: 32,
      },
    });

    // Create DB subnet group
    const dbSubnetGroup = new rds.SubnetGroup(this, 'DatabaseSubnetGroup', {
      vpc,
      description: 'Subnet group for multi-agent Aurora database',
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
    });

    // Create parameter group for Aurora PostgreSQL optimization
    const parameterGroup = new rds.ParameterGroup(this, 'DatabaseParameterGroup', {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_15_3,
      }),
      description: 'Parameter group for multi-agent Aurora PostgreSQL cluster',
      parameters: {
        'shared_preload_libraries': 'pg_stat_statements',
        'log_statement': 'all',
        'log_min_duration_statement': '1000',
        'max_connections': '200',
        'log_rotation_age': '1440',
        'log_rotation_size': '102400',
      },
    });

    // Create Aurora PostgreSQL cluster
    this.database = new rds.DatabaseCluster(this, 'Database', {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_15_3,
      }),
      credentials: rds.Credentials.fromSecret(this.databaseSecret),
      defaultDatabaseName: 'multiagent',
      vpc,
      subnetGroup: dbSubnetGroup,
      securityGroups: [databaseSecurityGroup],
      parameterGroup,

      // Writer instance configuration
      writer: rds.ClusterInstance.provisioned('writer', {
        instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MEDIUM),
        publiclyAccessible: false,
        enablePerformanceInsights: true,
        performanceInsightRetention: rds.PerformanceInsightRetention.DEFAULT,
      }),

      // Reader instances for high availability and read scaling
      // readers: [
      //   rds.ClusterInstance.provisioned('reader1', {
      //     instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MEDIUM),
      //     publiclyAccessible: false,
      //     enablePerformanceInsights: true,
      //     performanceInsightRetention: rds.PerformanceInsightRetention.DEFAULT,
      //   }),
      // ],

      // Backup and maintenance configuration
      backup: {
        retention: cdk.Duration.days(7),
        preferredWindow: '03:00-04:00',
      },
      preferredMaintenanceWindow: 'sun:04:00-sun:05:00',

      // Storage configuration
      storageEncrypted: true,
      deletionProtection: false, // Set to true for production

      // Monitoring configuration
      monitoringInterval: cdk.Duration.seconds(60),
      cloudwatchLogsExports: ['postgresql'],

      // Auto scaling configuration for Aurora Serverless v2 (optional)
      serverlessV2MinCapacity: 0.5,
      serverlessV2MaxCapacity: 2,
    });

    // Enable automatic minor version upgrades
    this.database.node.children.forEach((child) => {
      if (child instanceof rds.CfnDBInstance) {
        child.autoMinorVersionUpgrade = true;
      }
    });

    // Output database cluster endpoint
    new cdk.CfnOutput(this, 'DatabaseClusterEndpoint', {
      value: this.database.clusterEndpoint.hostname,
      description: 'Aurora cluster endpoint hostname',
      exportName: `${this.stackName}-DatabaseClusterEndpoint`,
    });

    // Output database reader endpoint
    new cdk.CfnOutput(this, 'DatabaseReaderEndpoint', {
      value: this.database.clusterReadEndpoint.hostname,
      description: 'Aurora cluster reader endpoint hostname',
      exportName: `${this.stackName}-DatabaseReaderEndpoint`,
    });

    // Output database port
    new cdk.CfnOutput(this, 'DatabasePort', {
      value: this.database.clusterEndpoint.port.toString(),
      description: 'Database port',
      exportName: `${this.stackName}-DatabasePort`,
    });

    // Output database secret ARN
    new cdk.CfnOutput(this, 'DatabaseSecretArn', {
      value: this.databaseSecret.secretArn,
      description: 'Database secret ARN',
      exportName: `${this.stackName}-DatabaseSecretArn`,
    });

    // Output database name
    new cdk.CfnOutput(this, 'DatabaseName', {
      value: 'multiagent',
      description: 'Database name',
      exportName: `${this.stackName}-DatabaseName`,
    });

    // Output cluster identifier
    new cdk.CfnOutput(this, 'DatabaseClusterIdentifier', {
      value: this.database.clusterIdentifier,
      description: 'Aurora cluster identifier',
      exportName: `${this.stackName}-DatabaseClusterIdentifier`,
    });
  }
}
