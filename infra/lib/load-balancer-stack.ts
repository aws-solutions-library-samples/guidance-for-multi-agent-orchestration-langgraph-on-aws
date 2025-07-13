import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as certificatemanager from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';

export interface LoadBalancerStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  albSecurityGroup: ec2.SecurityGroup;
}

export interface RouteConfig {
  agentName: string;
  pathPattern: string;
  port: number;
  priority: number;
}

export class LoadBalancerStack extends cdk.Stack {
  public readonly loadBalancer: elbv2.ApplicationLoadBalancer;
  public readonly targetGroups: Map<string, elbv2.ApplicationTargetGroup> = new Map();

  private readonly routeConfigs: RouteConfig[] = [
    {
      agentName: 'supervisor',
      pathPattern: '/*', // Catch all traffic
      port: 8000,
      priority: 10,
    },
  ];

  constructor(scope: Construct, id: string, props: LoadBalancerStackProps) {
    super(scope, id, props);

    const { vpc, albSecurityGroup } = props;

    // Create Application Load Balancer
    this.loadBalancer = new elbv2.ApplicationLoadBalancer(this, 'MultiAgentALB', {
      loadBalancerName: 'multi-agent-alb',
      vpc,
      internetFacing: true,
      securityGroup: albSecurityGroup,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC,
      },
    });

    // Create target groups for each agent
    this.createTargetGroups(vpc);

    // Create HTTP listener with routing rules
    this.createHttpListener();

    // Optionally create HTTPS listener (uncomment if you have SSL certificate)
    // this.createHttpsListener();

    // Output load balancer DNS name
    new cdk.CfnOutput(this, 'LoadBalancerDNS', {
      value: this.loadBalancer.loadBalancerDnsName,
      description: 'Application Load Balancer DNS name',
      exportName: `${this.stackName}-LoadBalancerDNS`,
    });

    // Output load balancer ARN
    new cdk.CfnOutput(this, 'LoadBalancerArn', {
      value: this.loadBalancer.loadBalancerArn,
      description: 'Application Load Balancer ARN',
      exportName: `${this.stackName}-LoadBalancerArn`,
    });

    // Output target group ARNs
    this.targetGroups.forEach((targetGroup, agentName) => {
      new cdk.CfnOutput(this, `${this.toPascalCase(agentName)}TargetGroupArn`, {
        value: targetGroup.targetGroupArn,
        description: `Target group ARN for ${agentName} agent`,
        exportName: `${this.stackName}-${this.toPascalCase(agentName)}TargetGroupArn`,
      });
    });
  }

  private createTargetGroups(vpc: ec2.Vpc): void {
    // Get unique agent names from route configs
    const uniqueAgents = [...new Set(this.routeConfigs.map(config => config.agentName))];

    uniqueAgents.forEach((agentName) => {
      const routeConfig = this.routeConfigs.find(config => config.agentName === agentName);
      if (!routeConfig) {
        throw new Error(`Route config not found for agent: ${agentName}`);
      }

      // Create target group
      const targetGroup = new elbv2.ApplicationTargetGroup(this, `${this.toPascalCase(agentName)}TargetGroup`, {
        targetGroupName: `${agentName}-tg`,
        port: routeConfig.port,
        protocol: elbv2.ApplicationProtocol.HTTP,
        vpc,
        targetType: elbv2.TargetType.IP,
        healthCheck: {
          enabled: true, // Must be true for IP target type
          healthyHttpCodes: '200-499', // Accept any HTTP response in valid range
          path: '/', // Use root path instead of /health
          protocol: elbv2.Protocol.HTTP,
          port: routeConfig.port.toString(),
          interval: cdk.Duration.seconds(300), // Check every 5 minutes (maximum allowed)
          timeout: cdk.Duration.seconds(120), // Long timeout (maximum allowed)
          healthyThresholdCount: 2, // Minimum required
          unhealthyThresholdCount: 10, // Maximum allowed - very forgiving
        },
        deregistrationDelay: cdk.Duration.seconds(30),
      });

      // Store target group for later use by ECS services
      this.targetGroups.set(agentName, targetGroup);
    });
  }

  private createHttpListener(): void {
    const listener = this.loadBalancer.addListener('HttpListener', {
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      open: true,
    });

    // Add default action (redirect to supervisor)
    const supervisorTargetGroup = this.targetGroups.get('supervisor');
    if (!supervisorTargetGroup) {
      throw new Error('Supervisor target group not found');
    }

    listener.addAction('DefaultAction', {
      action: elbv2.ListenerAction.forward([supervisorTargetGroup]),
    });

    // Add routing rules for each agent (excluding default route)
    this.routeConfigs
      .filter(config => config.pathPattern !== '/')
      .forEach((routeConfig) => {
        const targetGroup = this.targetGroups.get(routeConfig.agentName);
        if (!targetGroup) {
          throw new Error(`Target group not found for agent: ${routeConfig.agentName}`);
        }

        // Create unique action name by combining agent name and sanitized path pattern
        const sanitizedPath = routeConfig.pathPattern
          .replace(/[^a-zA-Z0-9]/g, '') // Remove special characters
          .replace(/^\*/, 'Wildcard') // Replace leading * with 'Wildcard'
          .replace(/\*$/, 'Wildcard'); // Replace trailing * with 'Wildcard'

        const actionName = `${this.toPascalCase(routeConfig.agentName)}${sanitizedPath}Action`;

        listener.addAction(actionName, {
          priority: routeConfig.priority,
          conditions: [
            elbv2.ListenerCondition.pathPatterns([routeConfig.pathPattern]),
          ],
          action: elbv2.ListenerAction.forward([targetGroup]),
        });
      });
  }

  private createHttpsListener(): void {
    // Uncomment and configure if you have an SSL certificate
    /*
    const certificate = certificatemanager.Certificate.fromCertificateArn(
      this,
      'Certificate',
      'arn:aws:acm:region:account:certificate/certificate-id'
    );

    const httpsListener = this.loadBalancer.addListener('HttpsListener', {
      port: 443,
      protocol: elbv2.ApplicationProtocol.HTTPS,
      certificates: [certificate],
      open: true,
    });

    // Add default action
    const supervisorTargetGroup = this.targetGroups.get('supervisor');
    if (supervisorTargetGroup) {
      httpsListener.addAction('DefaultHttpsAction', {
        action: elbv2.ListenerAction.forward([supervisorTargetGroup]),
      });
    }

    // Add routing rules
    this.routeConfigs
      .filter(config => config.pathPattern !== '/')
      .forEach((routeConfig) => {
        const targetGroup = this.targetGroups.get(routeConfig.agentName);
        if (targetGroup) {
          httpsListener.addAction(`${this.toPascalCase(routeConfig.agentName)}HttpsAction`, {
            priority: routeConfig.priority,
            conditions: [
              elbv2.ListenerCondition.pathPatterns([routeConfig.pathPattern]),
            ],
            action: elbv2.ListenerAction.forward([targetGroup]),
          });
        }
      });

    // Redirect HTTP to HTTPS
    this.loadBalancer.addRedirect({
      sourceProtocol: elbv2.ApplicationProtocol.HTTP,
      sourcePort: '80',
      targetProtocol: elbv2.ApplicationProtocol.HTTPS,
      targetPort: '443',
    });
    */
  }

  private toPascalCase(str: string): string {
    return str
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
  }
}
