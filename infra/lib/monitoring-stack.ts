import * as cdk from 'aws-cdk-lib';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import { Construct } from 'constructs';

export interface MonitoringStackProps extends cdk.StackProps {
  ecsServices: Map<string, ecs.FargateService>;
  loadBalancer: elbv2.ApplicationLoadBalancer;
  database: rds.DatabaseCluster;
}

export class MonitoringStack extends cdk.Stack {
  public readonly dashboard: cloudwatch.Dashboard;
  public readonly alarmTopic: sns.Topic;

  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    const { ecsServices, loadBalancer, database } = props;

    // Create SNS topic for alarms
    this.alarmTopic = new sns.Topic(this, 'AlarmTopic', {
      topicName: 'multi-agent-system-alarms',
      displayName: 'Multi-Agent System Alarms',
    });

    // Add email subscription (replace with your email)
    // this.alarmTopic.addSubscription(
    //   new snsSubscriptions.EmailSubscription('your-email@example.com')
    // );

    // Create CloudWatch Dashboard
    this.dashboard = new cloudwatch.Dashboard(this, 'MultiAgentDashboard', {
      dashboardName: 'MultiAgentSystem',
    });

    // Create monitoring for each ECS service
    this.createEcsMonitoring(ecsServices);

    // Create load balancer monitoring
    this.createLoadBalancerMonitoring(loadBalancer);

    // Create database monitoring
    this.createDatabaseMonitoring(database);

    // Create composite alarms
    this.createCompositeAlarms(ecsServices);

    // Output dashboard URL
    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${this.dashboard.dashboardName}`,
      description: 'CloudWatch Dashboard URL',
      exportName: `${this.stackName}-DashboardUrl`,
    });

    // Output SNS topic ARN
    new cdk.CfnOutput(this, 'AlarmTopicArn', {
      value: this.alarmTopic.topicArn,
      description: 'SNS topic ARN for alarms',
      exportName: `${this.stackName}-AlarmTopicArn`,
    });
  }

  private createEcsMonitoring(ecsServices: Map<string, ecs.FargateService>): void {
    const ecsWidgets: cloudwatch.IWidget[] = [];

    ecsServices.forEach((service, agentName) => {
      const clusterName = service.cluster.clusterName;
      const serviceName = service.serviceName;

      // CPU Utilization Metric
      const cpuMetric = new cloudwatch.Metric({
        namespace: 'AWS/ECS',
        metricName: 'CPUUtilization',
        dimensionsMap: {
          ServiceName: serviceName,
          ClusterName: clusterName,
        },
        statistic: 'Average',
        period: cdk.Duration.minutes(5),
      });

      // Memory Utilization Metric
      const memoryMetric = new cloudwatch.Metric({
        namespace: 'AWS/ECS',
        metricName: 'MemoryUtilization',
        dimensionsMap: {
          ServiceName: serviceName,
          ClusterName: clusterName,
        },
        statistic: 'Average',
        period: cdk.Duration.minutes(5),
      });

      // Running Task Count Metric
      const taskCountMetric = new cloudwatch.Metric({
        namespace: 'AWS/ECS',
        metricName: 'RunningTaskCount',
        dimensionsMap: {
          ServiceName: serviceName,
          ClusterName: clusterName,
        },
        statistic: 'Average',
        period: cdk.Duration.minutes(1),
      });

      // Create alarms
      const highCpuAlarm = new cloudwatch.Alarm(this, `${this.toPascalCase(agentName)}HighCpuAlarm`, {
        alarmName: `${agentName}-high-cpu`,
        alarmDescription: `High CPU utilization for ${agentName} agent`,
        metric: cpuMetric,
        threshold: 80,
        evaluationPeriods: 2,
        comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      });

      const highMemoryAlarm = new cloudwatch.Alarm(this, `${this.toPascalCase(agentName)}HighMemoryAlarm`, {
        alarmName: `${agentName}-high-memory`,
        alarmDescription: `High memory utilization for ${agentName} agent`,
        metric: memoryMetric,
        threshold: 80,
        evaluationPeriods: 2,
        comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      });

      const lowTaskCountAlarm = new cloudwatch.Alarm(this, `${this.toPascalCase(agentName)}LowTaskCountAlarm`, {
        alarmName: `${agentName}-low-task-count`,
        alarmDescription: `Low task count for ${agentName} agent`,
        metric: taskCountMetric,
        threshold: 1,
        evaluationPeriods: 1,
        comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        treatMissingData: cloudwatch.TreatMissingData.BREACHING,
      });

      // Add alarm actions
      [highCpuAlarm, highMemoryAlarm, lowTaskCountAlarm].forEach(alarm => {
        alarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
      });

      // Create widgets for dashboard
      const cpuWidget = new cloudwatch.GraphWidget({
        title: `${agentName} - CPU Utilization`,
        left: [cpuMetric],
        width: 12,
        height: 6,
      });

      const memoryWidget = new cloudwatch.GraphWidget({
        title: `${agentName} - Memory Utilization`,
        left: [memoryMetric],
        width: 12,
        height: 6,
      });

      const taskCountWidget = new cloudwatch.GraphWidget({
        title: `${agentName} - Running Tasks`,
        left: [taskCountMetric],
        width: 12,
        height: 6,
      });

      ecsWidgets.push(cpuWidget, memoryWidget, taskCountWidget);
    });

    // Add ECS widgets to dashboard
    this.dashboard.addWidgets(...ecsWidgets);
  }

  private createLoadBalancerMonitoring(loadBalancer: elbv2.ApplicationLoadBalancer): void {
    const lbName = loadBalancer.loadBalancerFullName;

    // Request Count Metric
    const requestCountMetric = new cloudwatch.Metric({
      namespace: 'AWS/ApplicationELB',
      metricName: 'RequestCount',
      dimensionsMap: {
        LoadBalancer: lbName,
      },
      statistic: 'Sum',
      period: cdk.Duration.minutes(5),
    });

    // Target Response Time Metric
    const responseTimeMetric = new cloudwatch.Metric({
      namespace: 'AWS/ApplicationELB',
      metricName: 'TargetResponseTime',
      dimensionsMap: {
        LoadBalancer: lbName,
      },
      statistic: 'Average',
      period: cdk.Duration.minutes(5),
    });

    // HTTP 5xx Error Count Metric
    const http5xxMetric = new cloudwatch.Metric({
      namespace: 'AWS/ApplicationELB',
      metricName: 'HTTPCode_ELB_5XX_Count',
      dimensionsMap: {
        LoadBalancer: lbName,
      },
      statistic: 'Sum',
      period: cdk.Duration.minutes(5),
    });

    // HTTP 4xx Error Count Metric
    const http4xxMetric = new cloudwatch.Metric({
      namespace: 'AWS/ApplicationELB',
      metricName: 'HTTPCode_Target_4XX_Count',
      dimensionsMap: {
        LoadBalancer: lbName,
      },
      statistic: 'Sum',
      period: cdk.Duration.minutes(5),
    });

    // Create alarms
    const highResponseTimeAlarm = new cloudwatch.Alarm(this, 'HighResponseTimeAlarm', {
      alarmName: 'alb-high-response-time',
      alarmDescription: 'High response time for Application Load Balancer',
      metric: responseTimeMetric,
      threshold: 2, // 2 seconds
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    const high5xxErrorAlarm = new cloudwatch.Alarm(this, 'High5xxErrorAlarm', {
      alarmName: 'alb-high-5xx-errors',
      alarmDescription: 'High 5xx error rate for Application Load Balancer',
      metric: http5xxMetric,
      threshold: 10,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Add alarm actions
    [highResponseTimeAlarm, high5xxErrorAlarm].forEach(alarm => {
      alarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
    });

    // Create widgets
    const requestCountWidget = new cloudwatch.GraphWidget({
      title: 'ALB - Request Count',
      left: [requestCountMetric],
      width: 12,
      height: 6,
    });

    const responseTimeWidget = new cloudwatch.GraphWidget({
      title: 'ALB - Response Time',
      left: [responseTimeMetric],
      width: 12,
      height: 6,
    });

    const errorRateWidget = new cloudwatch.GraphWidget({
      title: 'ALB - Error Rates',
      left: [http4xxMetric, http5xxMetric],
      width: 24,
      height: 6,
    });

    // Add widgets to dashboard
    this.dashboard.addWidgets(requestCountWidget, responseTimeWidget, errorRateWidget);
  }

  private createDatabaseMonitoring(database: rds.DatabaseCluster): void {
    const dbClusterId = database.clusterIdentifier;

    // CPU Utilization Metric for Aurora Cluster
    const dbCpuMetric = new cloudwatch.Metric({
      namespace: 'AWS/RDS',
      metricName: 'CPUUtilization',
      dimensionsMap: {
        DBClusterIdentifier: dbClusterId,
      },
      statistic: 'Average',
      period: cdk.Duration.minutes(5),
    });

    // Database Connections Metric for Aurora Cluster
    const dbConnectionsMetric = new cloudwatch.Metric({
      namespace: 'AWS/RDS',
      metricName: 'DatabaseConnections',
      dimensionsMap: {
        DBClusterIdentifier: dbClusterId,
      },
      statistic: 'Average',
      period: cdk.Duration.minutes(5),
    });

    // Aurora Capacity Units (ACU) for Serverless v2
    const auroraCapacityMetric = new cloudwatch.Metric({
      namespace: 'AWS/RDS',
      metricName: 'ServerlessDatabaseCapacity',
      dimensionsMap: {
        DBClusterIdentifier: dbClusterId,
      },
      statistic: 'Average',
      period: cdk.Duration.minutes(5),
    });

    // Read/Write IOPS metrics
    const readIopsMetric = new cloudwatch.Metric({
      namespace: 'AWS/RDS',
      metricName: 'ReadIOPS',
      dimensionsMap: {
        DBClusterIdentifier: dbClusterId,
      },
      statistic: 'Average',
      period: cdk.Duration.minutes(5),
    });

    const writeIopsMetric = new cloudwatch.Metric({
      namespace: 'AWS/RDS',
      metricName: 'WriteIOPS',
      dimensionsMap: {
        DBClusterIdentifier: dbClusterId,
      },
      statistic: 'Average',
      period: cdk.Duration.minutes(5),
    });

    // Create alarms
    const highDbCpuAlarm = new cloudwatch.Alarm(this, 'HighDbCpuAlarm', {
      alarmName: 'aurora-high-cpu',
      alarmDescription: 'High CPU utilization for Aurora database cluster',
      metric: dbCpuMetric,
      threshold: 80,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    const highConnectionsAlarm = new cloudwatch.Alarm(this, 'HighConnectionsAlarm', {
      alarmName: 'aurora-high-connections',
      alarmDescription: 'High connection count for Aurora database cluster',
      metric: dbConnectionsMetric,
      threshold: 80, // Adjust based on max_connections parameter
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    const highCapacityAlarm = new cloudwatch.Alarm(this, 'HighCapacityAlarm', {
      alarmName: 'aurora-high-capacity',
      alarmDescription: 'High capacity utilization for Aurora Serverless v2',
      metric: auroraCapacityMetric,
      threshold: 1.5, // 1.5 ACU threshold
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Add alarm actions
    [highDbCpuAlarm, highConnectionsAlarm, highCapacityAlarm].forEach(alarm => {
      alarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
    });

    // Create widgets
    const dbCpuWidget = new cloudwatch.GraphWidget({
      title: 'Aurora - CPU Utilization',
      left: [dbCpuMetric],
      width: 12,
      height: 6,
    });

    const dbConnectionsWidget = new cloudwatch.GraphWidget({
      title: 'Aurora - Database Connections',
      left: [dbConnectionsMetric],
      width: 12,
      height: 6,
    });

    const dbCapacityWidget = new cloudwatch.GraphWidget({
      title: 'Aurora - Serverless Capacity (ACU)',
      left: [auroraCapacityMetric],
      width: 12,
      height: 6,
    });

    const dbIopsWidget = new cloudwatch.GraphWidget({
      title: 'Aurora - Read/Write IOPS',
      left: [readIopsMetric, writeIopsMetric],
      width: 12,
      height: 6,
    });

    // Add widgets to dashboard
    this.dashboard.addWidgets(dbCpuWidget, dbConnectionsWidget, dbCapacityWidget, dbIopsWidget);
  }

  private createCompositeAlarms(ecsServices: Map<string, ecs.FargateService>): void {
    // Create a composite alarm that triggers if any critical service is down
    const serviceNames = Array.from(ecsServices.keys());
    const criticalServices = ['supervisor', 'order-management']; // Define critical services

    //   const criticalServiceAlarms = criticalServices
    //     .filter(serviceName => ecsServices.has(serviceName))
    //     .map(serviceName => `${serviceName}-low-task-count`);

    //   if (criticalServiceAlarms.length > 0) {
    //     new cloudwatch.CompositeAlarm(this, 'CriticalServicesDownAlarm', {
    //       // alarmName: 'critical-services-down',
    //       alarmDescription: 'One or more critical services are down',
    //       compositeAlarmRule: cloudwatch.AlarmRule.anyOf(
    //         ...criticalServiceAlarms.map(alarmName => 
    //           cloudwatch.AlarmRule.fromAlarm(
    //             cloudwatch.Alarm.fromAlarmArn(
    //               this,
    //               `${alarmName}-ref`,
    //               `arn:aws:cloudwatch:${this.region}:${this.account}:alarm:${alarmName}`
    //             ),
    //             cloudwatch.AlarmState.ALARM
    //           )
    //         )
    //       ),
    //       actionsEnabled: true,
    //     }).addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
    //   }
  }

  private toPascalCase(str: string): string {
    return str
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
  }
}
