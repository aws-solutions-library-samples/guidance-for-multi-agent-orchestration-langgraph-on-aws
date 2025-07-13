import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly albSecurityGroup: ec2.SecurityGroup;
  public readonly ecsSecurityGroup: ec2.SecurityGroup;
  public readonly databaseSecurityGroup: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create VPC with public and private subnets
    this.vpc = new ec2.Vpc(this, 'MultiAgentVPC', {
      ipAddresses: ec2.IpAddresses.cidr('10.0.0.0/16'),
      maxAzs: 2,
      natGateways: 2,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
      enableDnsHostnames: true,
      enableDnsSupport: true,
    });

    // Security Group for Application Load Balancer
    this.albSecurityGroup = new ec2.SecurityGroup(this, 'ALBSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for Application Load Balancer',
      allowAllOutbound: false,
    });

    // Allow HTTP and HTTPS traffic from internet
    this.albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      'Allow HTTP traffic from internet'
    );

    this.albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      'Allow HTTPS traffic from internet'
    );

    // Security Group for ECS Tasks
    this.ecsSecurityGroup = new ec2.SecurityGroup(this, 'ECSSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for ECS tasks',
      allowAllOutbound: true,
    });

    // Allow traffic from ALB to ECS tasks
    this.ecsSecurityGroup.addIngressRule(
      this.albSecurityGroup,
      ec2.Port.tcpRange(8000, 8010),
      'Allow traffic from ALB to ECS tasks'
    );

    // Allow ECS tasks to communicate with each other
    this.ecsSecurityGroup.addIngressRule(
      this.ecsSecurityGroup,
      ec2.Port.allTraffic(),
      'Allow ECS tasks to communicate with each other'
    );

    // Security Group for RDS Database
    this.databaseSecurityGroup = new ec2.SecurityGroup(this, 'DatabaseSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for RDS database',
      allowAllOutbound: false,
    });

    // Allow database access from ECS tasks
    this.databaseSecurityGroup.addIngressRule(
      this.ecsSecurityGroup,
      ec2.Port.tcp(5432),
      'Allow database access from ECS tasks'
    );

    // Add egress rule for ALB to ECS
    this.albSecurityGroup.addEgressRule(
      this.ecsSecurityGroup,
      ec2.Port.tcpRange(8000, 8010),
      'Allow ALB to reach ECS tasks'
    );

    // Output VPC ID for reference
    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      description: 'VPC ID for multi-agent system',
      exportName: `${this.stackName}-VpcId`,
    });

    // Output security group IDs
    new cdk.CfnOutput(this, 'ALBSecurityGroupId', {
      value: this.albSecurityGroup.securityGroupId,
      description: 'ALB Security Group ID',
      exportName: `${this.stackName}-ALBSecurityGroupId`,
    });

    new cdk.CfnOutput(this, 'ECSSecurityGroupId', {
      value: this.ecsSecurityGroup.securityGroupId,
      description: 'ECS Security Group ID',
      exportName: `${this.stackName}-ECSSecurityGroupId`,
    });

    new cdk.CfnOutput(this, 'DatabaseSecurityGroupId', {
      value: this.databaseSecurityGroup.securityGroupId,
      description: 'Database Security Group ID',
      exportName: `${this.stackName}-DatabaseSecurityGroupId`,
    });
  }
}
