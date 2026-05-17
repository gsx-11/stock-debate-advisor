import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as path from 'path';
import { Construct } from 'constructs';

interface ComputeStackProps extends cdk.StackProps {
  companiesTable: dynamodb.Table;
  financialReportsTable: dynamodb.Table;
  ohlcPricesTable: dynamodb.Table;
  debateResultsTable: dynamodb.Table;
}

/**
 * ComputeStack: Lambda functions and API Gateway for debate orchestration
 * - Data Uploader Lambda: Automatically uploads stock data from data_store to DynamoDB on deployment
 * - Debate Lambda: Orchestrates multi-agent debate via Bedrock Claude Sonnet 3.5
 * - Health Lambda: Readiness check
 * - API Gateway: REST endpoints with CORS
 */
export class ComputeStack extends cdk.Stack {
  readonly debateApi: apigateway.RestApi;
  readonly debateLambda: lambda.Function;
  readonly dataUploaderLambda: lambda.Function;

  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    // IAM Role for Lambda: Bedrock, DynamoDB, CloudWatch
    const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      description: 'Execution role for Stock Debate Lambda functions'
    });

    // Bedrock permissions (Claude Sonnet 3.5)
    lambdaRole.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream'
        ],
        resources: ['arn:aws:bedrock:*::foundation-model/anthropic.claude-*'],
        effect: iam.Effect.ALLOW
      })
    );

    // DynamoDB permissions for all tables
    props.companiesTable.grantReadData(lambdaRole);
    props.financialReportsTable.grantReadData(lambdaRole);
    props.ohlcPricesTable.grantReadData(lambdaRole);
    props.debateResultsTable.grantReadWriteData(lambdaRole);
    
    // Additional write permissions for data uploader
    props.companiesTable.grantWriteData(lambdaRole);
    props.financialReportsTable.grantWriteData(lambdaRole);
    props.ohlcPricesTable.grantWriteData(lambdaRole);

    // Data Uploader Lambda - uploads data_store to DynamoDB on deployment
    this.dataUploaderLambda = new lambda.Function(this, 'DataUploaderLambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'data_uploader.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../data_store'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp lambda/data_uploader.py /asset-output/ && cp -r data /asset-output/'
          ]
        }
      }),
      timeout: cdk.Duration.seconds(900), // 15 minutes for data upload
      memorySize: 1024,
      ephemeralStorageSize: cdk.Size.mebibytes(2048),
      role: lambdaRole,
      environment: {
        COMPANIES_TABLE: props.companiesTable.tableName,
        FINANCIAL_REPORTS_TABLE: props.financialReportsTable.tableName,
        OHLC_PRICES_TABLE: props.ohlcPricesTable.tableName
      },
      description: 'Automatically upload stock data from data_store to DynamoDB'
    });
    cdk.Tags.of(this.dataUploaderLambda).add('Component', 'DataStore');
    cdk.Tags.of(this.dataUploaderLambda).add('Purpose', 'DataUpload');

    // Invoke data uploader Lambda after deployment to populate DynamoDB
    const dataUploaderProvider = new cdk.custom_resources.Provider(this, 'DataUploaderProvider', {
      onEventHandler: this.dataUploaderLambda,
      isCompleteHandler: new lambda.Function(this, 'DataUploaderCompleteHandler', {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: 'index.handler',
        code: lambda.Code.fromInline(`
import json
import boto3

def handler(event, context):
    return {
        'IsComplete': True,
        'Data': {
            'Status': 'DataUploadTriggered'
        }
    }
        `)
      })
    });

    // Custom resource to trigger data upload on stack deployment
    new cdk.CustomResource(this, 'DataUploadResource', {
      serviceToken: dataUploaderProvider.serviceToken,
      properties: {
        COMPANIES_TABLE: props.companiesTable.tableName,
        FINANCIAL_REPORTS_TABLE: props.financialReportsTable.tableName,
        OHLC_PRICES_TABLE: props.ohlcPricesTable.tableName
      }
    });

    // Debate Lambda function - uses Claude Sonnet 3.5 via Bedrock
    this.debateLambda = new lambda.Function(this, 'DebateLambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'src.handlers.index.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../ai-service'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r deps/requirements-prod.txt -t /asset-output && cp -r src /asset-output/'
          ]
        }
      }),
      timeout: cdk.Duration.seconds(900), // 15 minutes for multi-round debates
      memorySize: 1024,
      ephemeralStorageSize: cdk.Size.mebibytes(1024),
      role: lambdaRole,
      environment: {
        COMPANIES_TABLE: props.companiesTable.tableName,
        FINANCIAL_REPORTS_TABLE: props.financialReportsTable.tableName,
        OHLC_PRICES_TABLE: props.ohlcPricesTable.tableName,
        DEBATE_RESULTS_TABLE: props.debateResultsTable.tableName,
        BEDROCK_MODEL: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
        AWS_LAMBDA_LOG_LEVEL: 'INFO'
      },
      description: 'Multi-agent stock debate v3.0 (5 agents, price conditions, Auto/Human mode)'
    });
    cdk.Tags.of(this.debateLambda).add('Component', 'AI-Service');
    cdk.Tags.of(this.debateLambda).add('Purpose', 'DebateOrchestration');
    cdk.Tags.of(this.debateLambda).add('Model', 'Claude-Sonnet-3.5');
    cdk.Tags.of(this.debateLambda).add('Version', '3.0');

    // Health check Lambda
    const healthLambda = new lambda.Function(this, 'HealthLambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'src.handlers.index.health_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../ai-service'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r deps/requirements-prod.txt -t /asset-output && cp -r src /asset-output/'
          ]
        }
      }),
      timeout: cdk.Duration.seconds(30),
      memorySize: 128,
      role: lambdaRole,
      environment: {
        COMPANIES_TABLE: props.companiesTable.tableName,
        AWS_LAMBDA_LOG_LEVEL: 'INFO'
      },
      description: 'Health check for Stock Debate API'
    });
    cdk.Tags.of(healthLambda).add('Component', 'AI-Service');
    cdk.Tags.of(healthLambda).add('Purpose', 'HealthCheck');

    // API Gateway
    this.debateApi = new apigateway.RestApi(this, 'StockDebateApi', {
      restApiName: 'Stock Debate Advisor API',
      description: 'Multi-agent stock analysis debate system with Claude Sonnet 3.5',
      deploy: true,
      deployOptions: {
        stageName: 'prod',
        throttlingBurstLimit: 100,
        throttlingRateLimit: 50,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: ['GET', 'POST', 'OPTIONS'],
        allowHeaders: ['Content-Type', 'Authorization'],
        statusCode: 200
      }
    });

    // Health endpoint: GET /health
    const healthResource = this.debateApi.root.addResource('health');
    healthResource.addMethod('GET', new apigateway.LambdaIntegration(healthLambda), {
      methodResponses: [{ statusCode: '200' }]
    });

    // Legacy debate endpoint: POST /debate
    const debateResource = this.debateApi.root.addResource('debate');
    const debateLambdaProxy = new apigateway.LambdaIntegration(this.debateLambda);
    debateResource.addMethod('POST', debateLambdaProxy);

    // ── v3.0 API Routes ──────────────────────────────────────────
    const apiResource = this.debateApi.root.addResource('api');
    const v1Resource = apiResource.addResource('v1');

    // POST /api/v1/debate/start
    const v1DebateResource = v1Resource.addResource('debate');
    const v1StartResource = v1DebateResource.addResource('start');
    v1StartResource.addMethod('POST', debateLambdaProxy);

    // POST /api/v1/debate/continue
    const v1ContinueResource = v1DebateResource.addResource('continue');
    v1ContinueResource.addMethod('POST', debateLambdaProxy);

    // GET /api/v1/debate/status/{session_id}
    const v1StatusResource = v1DebateResource.addResource('status');
    const v1StatusIdResource = v1StatusResource.addResource('{session_id}');
    v1StatusIdResource.addMethod('GET', debateLambdaProxy);

    // GET /api/v1/debate/result/{session_id}
    const v1ResultResource = v1DebateResource.addResource('result');
    const v1ResultIdResource = v1ResultResource.addResource('{session_id}');
    v1ResultIdResource.addMethod('GET', debateLambdaProxy);

    // GET /api/v1/companies
    const v1CompaniesResource = v1Resource.addResource('companies');
    v1CompaniesResource.addMethod('GET', debateLambdaProxy);

    // GET /api/v1/company/{symbol}
    const v1CompanyResource = v1Resource.addResource('company');
    const v1CompanySymbolResource = v1CompanyResource.addResource('{symbol}');
    v1CompanySymbolResource.addMethod('GET', debateLambdaProxy);

    // POST /api/v2/query (LangGraph)
    const v2Resource = apiResource.addResource('v2');
    const v2QueryResource = v2Resource.addResource('query');
    v2QueryResource.addMethod('POST', debateLambdaProxy);

    // API Gateway outputs
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: this.debateApi.url,
      exportName: 'StockDebateApiEndpoint',
      description: 'Stock Debate API endpoint'
    });

    new cdk.CfnOutput(this, 'HealthEndpoint', {
      value: `${this.debateApi.url}health`,
      description: 'Health check endpoint'
    });

    new cdk.CfnOutput(this, 'DebateEndpoint', {
      value: `${this.debateApi.url}debate`,
      description: 'Debate analysis endpoint'
    });

    new cdk.CfnOutput(this, 'DataUploaderLambdaArn', {
      value: this.dataUploaderLambda.functionArn,
      exportName: 'DataUploaderLambdaArn',
      description: 'Data Uploader Lambda ARN for manual invocation'
    });
  }
}
