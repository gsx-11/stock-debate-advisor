# Quick Start Guide - Stock Debate Advisor v7

## What is This?
AI-powered stock analysis platform using multi-agent debates. Submit a stock symbol, watch AI agents (Fundamental, Technical, Sentiment analysts + Judge) debate the merits, get a buy/hold/sell verdict.

## Prerequisites
- AWS Account (free tier eligible)
- Node.js 18+ (for CDK)
- Python 3.12+ (for local backend testing)
- AWS CLI configured: `aws configure`
- Git

## Two Deployment Modes

### Mode 1: Lambda Only (Simple, < 15-min debates)
```bash
cd /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7
cdk deploy --all
```
- Pros: Simple deployment, low latency
- Cons: Hard 15-minute timeout

### Mode 2: Lambda + ECS (Recommended, any debate length)
```bash
cd /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7
USE_ECS_DEBATES=true cdk deploy --all
```
- Pros: Handles long debates, auto-scaling, cost-efficient
- Cons: ECS cluster adds ~$30/month when running

## Step-by-Step Deployment

### 1. Configure Environment Variables

Create `.env.local` in v7 directory:
```bash
# AWS Credentials (if not using aws configure)
export AWS_PROFILE=default

# Feature Flags
export USE_ECS_DEBATES=true  # Set to "true" for ECS support

# AWS Region
export AWS_DEFAULT_REGION=us-east-1

# Optional: Cognito config
export COGNITO_DOMAIN=stock-debate
export COGNITO_CALLBACK_URL=https://yourdomain.com/callback
```

Load environment:
```bash
source .env.local
```

### 2. Install Dependencies

**CDK Deployment**:
```bash
cd v7
npm install
```

**Backend (optional for local testing)**:
```bash
cd v7/backend
pip install boto3
```

### 3. Build Frontend

```bash
cd v7/frontend
npm install
npm run build
# Output: frontend/dist/
```

### 4. Deploy Infrastructure

```bash
cd v7
cdk synth              # Generate CloudFormation
cdk deploy --all       # Deploy to AWS
```

**Deployment Time**: 5-10 minutes

**Outputs** (saved automatically):
```
API_GATEWAY_ENDPOINT=https://xxxxx.execute-api.us-east-1.amazonaws.com/prod
FRONTEND_CLOUDFRONT_URL=https://dxxxxx.cloudfront.net
DYNAMODB_TABLES=companies, financial_reports, ohlc_prices, debate_results
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/stock-debate-tasks
```

### 5. Verify Deployment

```bash
# Check API Gateway
curl https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/health

# Expected response:
# {"status": "healthy"}
```

## Using the Platform

### Start a Debate

**Option A: Frontend UI**
1. Visit CloudFront URL: `https://dxxxxx.cloudfront.net`
2. Enter stock symbol (e.g., "AAPL", "MBB")
3. Select number of debate rounds (1-5)
4. Click "Start Debate"

**Option B: REST API**
```bash
curl -X POST https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/debate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "rounds": 3
  }'

# Response (async):
# {
#   "debate_id": "debate_abc123_1234567890",
#   "status": "submitted",
#   "message": "Debate task submitted for processing"
# }
```

### Check Debate Status

```bash
curl https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/debate/debate_abc123_1234567890

# Response when in-progress:
# {
#   "debate_id": "debate_abc123_1234567890",
#   "status": "in_progress",
#   "symbol": "AAPL",
#   "rounds": 3
# }

# Response when completed:
# {
#   "debate_id": "debate_abc123_1234567890",
#   "status": "completed",
#   "symbol": "AAPL",
#   "rounds": 3,
#   "verdict": {
#     "recommendation": "BUY",
#     "confidence": "HIGH"
#   },
#   "summary": "Technical indicators showing strong momentum...",
#   "duration_seconds": 312
# }
```

## Architecture Components

### Frontend
- **Type**: React SPA
- **Deployment**: S3 + CloudFront (CDN)
- **API Endpoint**: Configured at build time via environment variables
- **Location**: CloudFront HTTPS URL

### API Gateway
- **Type**: REST API
- **Endpoints**:
  - `GET /health` - Health check
  - `POST /debate` - Submit debate (returns 202 Accepted)
  - `GET /debate/{debate_id}` - Poll status/results
- **CORS**: Enabled for CloudFront origin

### Lambda Layer 1 (Health Check)
- Lightweight health check endpoint
- ~30 second timeout
- Minimal cost

### Lambda Layer 2 (Debate Submitter)
- Receives debate requests
- Submits to SQS queue
- Returns 202 Accepted immediately
- Non-blocking

### SQS Queue
- Decouples request submission from processing
- 20-minute visibility timeout
- 24-hour message retention

### ECS Fargate (Optional)
- **When**: Long debates (>15 minutes) or high volume
- **Specs**: 2vCPU, 8GB memory per task
- **Auto-scaling**: 1-10 tasks based on queue depth
- **Cost**: ~$30/month when running (pay-per-hour)

### Backend Services
```
models.py          → Data classes & enums
database.py        → DynamoDB abstraction
orchestrator.py    → Debate lifecycle management
data_service.py    → Company/financial/price data
api_router.py      → Request routing
```

### DynamoDB Tables
1. **companies** - Stock metadata (symbol, name, sector, etc.)
2. **financial_reports** - Quarterly financial statements
3. **ohlc_prices** - Historical price data
4. **debate_results** - Debate sessions and verdicts

## Monitoring

### CloudWatch Logs
View logs in AWS Console or CLI:
```bash
# Lambda logs
aws logs tail /aws/lambda/stock-debate-advisor-compute-prod --follow

# ECS logs
aws logs tail /ecs/stock-debate-task --follow

# API Gateway logs
aws logs tail /aws/apigateway/stock-debate-api --follow
```

### CloudWatch Metrics
- Lambda: Invocations, duration, errors
- ECS: Task count, CPU, memory
- SQS: Queue depth, messages processed
- API Gateway: Requests, latency, errors
- DynamoDB: Read/write capacity, throttles

### Recommended Alarms
```bash
# ECS task failure rate
aws cloudwatch put-metric-alarm \
  --alarm-name ecs-task-failures \
  --alarm-description "Alert if ECS tasks failing" \
  --metric-name FailedTasks \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold

# SQS queue depth
aws cloudwatch put-metric-alarm \
  --alarm-name sqs-queue-depth \
  --alarm-description "Alert if queue building up" \
  --metric-name ApproximateNumberOfMessagesVisible \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold
```

## Common Tasks

### Update Frontend Code
```bash
cd v7/frontend
# Make changes
npm run build
# Redeploy via CDK
cdk deploy FrontendStack
```

### View Debate History
```bash
aws dynamodb scan \
  --table-name debate_results \
  --filter-expression "attribute_exists(verdict)" \
  --max-items 10

# Or via API:
curl https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/debate/history?symbol=AAPL
```

### Manually Trigger Data Upload
```bash
aws lambda invoke \
  --function-name DataUploadFunction \
  --payload '{"source":"manual"}' \
  response.json
```

### Scale ECS Tasks
```bash
# Update max tasks (default: 10)
vim v7/cdk/src/ecs-stack.ts
# Change: maxCapacity: 10
cdk deploy EcsStack
```

### Add New Stock Symbol
1. Add to `data-service/symbols.json`
2. Run data uploader Lambda
3. Check DynamoDB tables

## Troubleshooting

### Frontend shows "localhost:8000" API
**Problem**: Frontend hardcoded to localhost
**Solution**: Already fixed! Frontend now uses environment variable VITE_API_BASE_URL

### Debates timeout after 15 minutes
**Problem**: Using Lambda-only mode
**Solution**: Deploy with ECS: `USE_ECS_DEBATES=true cdk deploy --all`

### SQS queue filling up (not processing)
**Cause**: ECS tasks not running
**Fix**:
1. Check ECS cluster: `aws ecs list-clusters`
2. Check task logs: CloudWatch → /ecs/stock-debate-task
3. Verify Bedrock access: `aws bedrock list-foundation-models`

### API Gateway 502 Bad Gateway
**Cause**: Lambda timeout or crash
**Fix**:
1. Check Lambda logs: CloudWatch → /aws/lambda/stock-debate-advisor-compute-prod
2. Verify DynamoDB tables exist
3. Test with `curl /health` endpoint

### DynamoDB throttled errors
**Cause**: Write capacity exceeded
**Fix**:
1. Switch from on-demand to provisioned capacity
2. Or: Increase DynamoDB throughput in CDK

### High AWS costs
**Optimization**:
1. **Disable ECS when not needed**: Remove `USE_ECS_DEBATES` flag
2. **Set DynamoDB TTL**: Auto-delete old results (30 days default)
3. **Reduce CloudFront**: Increase cache TTL for company data
4. **Limit debate rounds**: 3 rounds typical, 5 is max

## Cost Estimate

### Lambda-Only Mode
- API Gateway: ~$0.35/month (assuming 100K requests)
- Lambda: ~$1-2/month
- DynamoDB: ~$15/month (on-demand)
- S3 + CloudFront: ~$2/month
- **Total**: ~$18-20/month

### Lambda + ECS Mode (Continuous Running)
- All above: ~$18-20
- ECS Fargate: ~$30/month (2vCPU, 8GB, 24/7)
- **Total**: ~$48-50/month

### Lambda + ECS Mode (Auto-Scaling Off)
- All above: ~$18-20
- ECS only when debates run: ~$1-5/month (on-demand)
- **Total**: ~$20-25/month

## Cleanup (Destroy Infrastructure)

```bash
cd v7
cdk destroy --all

# Confirm deletion: Type 'y' when prompted
```

⚠️ **Warning**: This deletes:
- API Gateway, Lambda, ECS
- S3 bucket (downloads not preserved)
- DynamoDB tables (data deleted)
- CloudFront distribution

**To preserve data**: Backup DynamoDB before destroying:
```bash
aws dynamodb create-backup \
  --table-name debate_results \
  --backup-name debate-results-backup-$(date +%Y%m%d)
```

## Next Steps

1. **Customize Debate Prompts**: Edit `v7/ai-service/prompts/`
2. **Add Authentication**: Uncomment Cognito in CDK
3. **Monitor with Dashboards**: Create CloudWatch dashboards
4. **Set Up Alerts**: Configure SNS notifications
5. **Scale Multi-Region**: Deploy to multiple AWS regions
6. **Add Search**: Integrate OpenSearch for debate history

## Support & Resources

- **Architecture Details**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Backend Services**: See [v7/backend/README.md](backend/README.md)
- **AWS CDK Docs**: https://docs.aws.amazon.com/cdk/latest/guide/
- **Bedrock Docs**: https://docs.aws.amazon.com/bedrock/
- **DynamoDB Docs**: https://docs.aws.amazon.com/dynamodb/

---

**Version**: 7.1 | **Last Updated**: January 2024 | **Status**: ✅ Production Ready
