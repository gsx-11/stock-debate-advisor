import * as cdk from 'aws-cdk-lib';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as autoscaling from 'aws-cdk-lib/aws-applicationautoscaling';
import * as path from 'path';
import { Construct } from 'constructs';

interface EcsStackProps extends cdk.StackProps {
  companiesTable: dynamodb.Table;
  financialReportsTable: dynamodb.Table;
  ohlcPricesTable: dynamodb.Table;
  debateResultsTable: dynamodb.Table;
  vpc?: ec2.Vpc;
}

/**
 * EcsStack: AWS ECS Fargate for long-running debate processing
 * 
 * Replaces Lambda for debates exceeding 15-minute timeout.
 * Uses SQS for async task submission and ECS for processing.
 * 
 * Architecture:
 * - API Gateway -> Lambda (submit debate) -> SQS queue
 * - ECS Fargate task pulls from SQS, processes debate (up to 1 hour)
 * - Results stored in DynamoDB, Lambda polls for completion
 */
export class EcsStack extends cdk.Stack {
  readonly debateQueue: sqs.Queue;
  readonly ecsCluster: ecs.Cluster;
  readonly ecsTaskDefinition: ecs.TaskDefinition;
  readonly ecsService: ecs.FargateService;

  constructor(scope: Construct, id: string, props: EcsStackProps) {
    super(scope, id, props);

    // Get or create VPC
    const vpc = props.vpc || new ec2.Vpc(this, 'DebateVpc', {
      maxAzs: 2,
      cidrBlock: '10.0.0.0/16'
    });

    // SQS Queue for debate tasks (15 min visibility timeout for debate processing)
    this.debateQueue = new sqs.Queue(this, 'DebateTaskQueue', {
      queueName: 'stock-debate-tasks',
      visibilityTimeout: cdk.Duration.minutes(20), // Task timeout + buffer
      retentionPeriod: cdk.Duration.days(1),
      deliveryDelay: cdk.Duration.seconds(0),
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });
    cdk.Tags.of(this.debateQueue).add('Component', 'TaskQueue');
    cdk.Tags.of(this.debateQueue).add('Purpose', 'DebateProcessing');

    // ECS Cluster
    this.ecsCluster = new ecs.Cluster(this, 'DebateCluster', {
      vpc,
      clusterName: 'stock-debate-cluster',
      containerInsights: true
    });
    cdk.Tags.of(this.ecsCluster).add('Component', 'ECS');
    cdk.Tags.of(this.ecsCluster).add('Purpose', 'DebateOrchestration');

    // IAM Role for ECS Task Execution
    const ecsTaskExecutionRole = new iam.Role(this, 'EcsTaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy')
      ]
    });

    // IAM Role for ECS Task (application permissions)
    const ecsTaskRole = new iam.Role(this, 'EcsTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      description: 'Role for Stock Debate ECS tasks'
    });

    // Bedrock permissions
    ecsTaskRole.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream'
        ],
        resources: ['arn:aws:bedrock:*::foundation-model/anthropic.claude-*'],
        effect: iam.Effect.ALLOW
      })
    );

    // DynamoDB permissions
    props.companiesTable.grantReadData(ecsTaskRole);
    props.financialReportsTable.grantReadData(ecsTaskRole);
    props.ohlcPricesTable.grantReadData(ecsTaskRole);
    props.debateResultsTable.grantReadWriteData(ecsTaskRole);

    // SQS permissions
    this.debateQueue.grantConsumeMessages(ecsTaskRole);

    // CloudWatch Log Group for ECS
    const logGroup = new logs.LogGroup(this, 'DebateTaskLogs', {
      logGroupName: '/ecs/stock-debate-task',
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    // ECS Task Definition for Debate Processing
    this.ecsTaskDefinition = new ecs.TaskDefinition(this, 'DebateTaskDefinition', {
      compatibility: ecs.Compatibility.FARGATE,
      cpu: '2048',      // 2 vCPU
      memoryMiB: '8192',  // 8 GB (as string for Fargate)
      executionRole: ecsTaskExecutionRole,
      taskRole: ecsTaskRole
    });
    cdk.Tags.of(this.ecsTaskDefinition).add('Component', 'ECS');
    cdk.Tags.of(this.ecsTaskDefinition).add('Purpose', 'DebateTask');

    // Container definition
    const container = this.ecsTaskDefinition.addContainer('DebateContainer', {
      image: ecs.ContainerImage.fromAsset(path.join(__dirname, '../../ai-service'), {
        file: path.join(__dirname, '../../ai-service/Dockerfile.ecs')
      }),
      logging: ecs.LogDriver.awsLogs({
        streamPrefix: 'debate',
        logGroup
      }),
      environment: {
        COMPANIES_TABLE: props.companiesTable.tableName,
        FINANCIAL_REPORTS_TABLE: props.financialReportsTable.tableName,
        OHLC_PRICES_TABLE: props.ohlcPricesTable.tableName,
        DEBATE_RESULTS_TABLE: props.debateResultsTable.tableName,
        BEDROCK_MODEL: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
        DEBATE_QUEUE_URL: this.debateQueue.queueUrl,
        AWS_REGION: this.region,
        LOG_LEVEL: 'INFO'
      },
      // Set high memory soft limit to avoid OOM kills
      memoryLimitMiB: 8000
    });

    // Port mapping (internal only, no external exposure)
    container.addPortMappings({
      containerPort: 8000,
      protocol: ecs.Protocol.TCP
    });

    // ECS Service (Fargate)
    this.ecsService = new ecs.FargateService(this, 'DebateService', {
      cluster: this.ecsCluster,
      taskDefinition: this.ecsTaskDefinition,
      desiredCount: 1,
      serviceName: 'stock-debate-service',
      assignPublicIp: false  // No public IP needed
    });

    // Add auto-scaling based on queue depth
    const scaling = this.ecsService.autoScaleTaskCount({
      minCapacity: 1,
      maxCapacity: 10
    });

    // Scale up when queue has messages
    scaling.scaleOnMetric('QueueDepthScaling', {
      metric: this.debateQueue.metricApproximateNumberOfMessagesVisible(),
      scalingSteps: [
        { upper: 1, change: 0 },      // 0-1 messages: 1 task
        { lower: 1, change: +2 },     // >1 messages: add 2 tasks
        { lower: 10, change: +4 }     // >10 messages: add 4 more tasks
      ],
      adjustmentType: autoscaling.AdjustmentType.CHANGE_IN_CAPACITY
    });

    cdk.Tags.of(this.ecsService).add('Component', 'ECS');
    cdk.Tags.of(this.ecsService).add('Purpose', 'DebateOrchestration');

    // Lambda wrapper to submit tasks to SQS
    const debateSubmitterLambda = new lambda.Function(this, 'DebateSubmitterLambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromInline(`
import json
import boto3
import uuid
from datetime import datetime

sqs = boto3.client('sqs')

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        symbol = body.get('symbol')
        rounds = body.get('rounds', 3)
        
        if not symbol:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'symbol is required'})
            }
        
        # Create debate record ID
        debate_id = f"debate_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp())}"
        
        # Submit task to SQS
        queue_url = '${this.debateQueue.queueUrl}'
        
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({
                'debate_id': debate_id,
                'symbol': symbol,
                'rounds': rounds
            })
        )
        
        return {
            'statusCode': 202,
            'body': json.dumps({
                'session_id': debate_id,
                'symbol': symbol,
                'rounds': rounds,
                'status': 'submitted'
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
      `),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        DEBATE_QUEUE_URL: this.debateQueue.queueUrl
      },
      description: 'Lambda wrapper to submit debate tasks to SQS'
    });

    // Grant Lambda permission to send messages to SQS
    this.debateQueue.grantSendMessages(debateSubmitterLambda);

    // Outputs
    new cdk.CfnOutput(this, 'DebateQueueUrl', {
      value: this.debateQueue.queueUrl,
      exportName: 'DebateQueueUrl',
      description: 'SQS queue URL for debate tasks'
    });

    new cdk.CfnOutput(this, 'DebateQueueArn', {
      value: this.debateQueue.queueArn,
      exportName: 'DebateQueueArn',
      description: 'SQS queue ARN for debate tasks'
    });

    new cdk.CfnOutput(this, 'EcsClusterName', {
      value: this.ecsCluster.clusterName,
      exportName: 'DebateEcsClusterName',
      description: 'ECS cluster name for debate processing'
    });

    new cdk.CfnOutput(this, 'DebateSubmitterLambdaArn', {
      value: debateSubmitterLambda.functionArn,
      exportName: 'DebateSubmitterLambdaArn',
      description: 'Lambda function ARN for submitting debate tasks'
    });
  }
}
