# AuditIQ Cloud — AWS Deployment Guide

This guide provides a step-by-step walkthrough for deploying **AuditIQ Cloud** into an AWS account.

---

## 1. Prerequisites & Account Requirements

- An active **AWS Account** with administrative permissions to create resources.
- **AWS CLI v2** installed and configured (`aws configure`).
- **Docker** installed for building container images.
- Access to **Amazon Bedrock Foundation Models** (specifically Anthropic Claude 3 Haiku or Amazon Nova).

---

## 2. Region Selection

Recommended regions where Amazon Bedrock, App Runner, S3, DynamoDB, and Cognito are simultaneously available:
- `us-east-1` (US East, N. Virginia) **[Recommended]**
- `us-west-2` (US West, Oregon)
- `eu-central-1` (Europe, Frankfurt)

Set your target region:
```bash
export AWS_REGION="us-east-1"
```

---

## 3. Amazon S3 Bucket Creation

Create a private S3 bucket for datasets, manifests, and PDF audit reports:

```bash
BUCKET_NAME="auditiq-cloud-datasets-$(aws sts get-caller-identity --query Account --output text)"

# Create bucket
aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$AWS_REGION"

# Block all public access (Critical Security Requirement)
aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Enable AES-256 default server-side encryption
aws s3api put-bucket-encryption \
    --bucket "$BUCKET_NAME" \
    --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'
```

---

## 4. Amazon DynamoDB Tables Creation

AuditIQ Cloud requires two DynamoDB tables with on-demand capacity:

### A. Datasets Metadata Table (`AuditIQDatasets`)
```bash
aws dynamodb create-table \
    --table-name AuditIQDatasets \
    --attribute-definitions AttributeName=dataset_id,AttributeType=S \
    --key-schema AttributeName=dataset_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$AWS_REGION"
```

### B. Persistent Audit Runs Table (`AuditIQAuditRuns`)
```bash
aws dynamodb create-table \
    --table-name AuditIQAuditRuns \
    --attribute-definitions AttributeName=run_id,AttributeType=S \
    --key-schema AttributeName=run_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$AWS_REGION"
```

---

## 5. Amazon Cognito User Pool Setup

Create a user pool to authenticate audit teams:

```bash
# 1. Create User Pool
USER_POOL_ID=$(aws cognito-idp create-user-pool \
    --pool-name "AuditIQCloudUsers" \
    --policies '{"PasswordPolicy":{"MinimumLength":8,"RequireUppercase":true,"RequireLowercase":true,"RequireNumbers":true,"RequireSymbols":false}}' \
    --auto-verified-attributes email \
    --query 'UserPool.Id' \
    --output text)

# 2. Create User Pool Client (for web application)
APP_CLIENT_ID=$(aws cognito-idp create-user-pool-client \
    --user-pool-id "$USER_POOL_ID" \
    --client-name "AuditIQCloudWebClient" \
    --no-generate-secret \
    --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
    --query 'UserPoolClient.ClientId' \
    --output text)

echo "Cognito User Pool ID: $USER_POOL_ID"
echo "Cognito App Client ID: $APP_CLIENT_ID"
```

---

## 6. Amazon Bedrock Model Access

1. Navigate to the **AWS Console** -> **Amazon Bedrock** -> **Model access**.
2. Request access to **Anthropic Claude 3 Haiku** (`anthropic.claude-3-haiku-20240307-v1:0`).
3. Model access is granted almost immediately for serverless on-demand inference.

---

## 7. App Runner IAM Instance Role

Create a least-privilege IAM role that allows the backend container to interact only with the required AWS resources:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::auditiq-cloud-datasets-*",
        "arn:aws:s3:::auditiq-cloud-datasets-*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Scan",
        "dynamodb:Query",
        "dynamodb:DescribeTable"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/AuditIQDatasets",
        "arn:aws:dynamodb:*:*:table/AuditIQAuditRuns"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:*:*:foundation-model/*"
    }
  ]
}
```

---

## 8. Backend Deployment on AWS App Runner

### A. Push Docker Container to Amazon ECR
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/auditiq-backend"

# Create ECR repository
aws ecr create-repository --repository-name auditiq-backend --region "$AWS_REGION"

# Login to ECR
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Build and push container
cd backend
docker build -t auditiq-backend .
docker tag auditiq-backend:latest "$ECR_URI:latest"
docker push "$ECR_URI:latest"
```

### B. Launch App Runner Service
Create the App Runner service configuring the environment variables:
- `AWS_REGION` = `$AWS_REGION`
- `S3_BUCKET` = `$BUCKET_NAME`
- `DYNAMODB_DATASETS_TABLE` = `AuditIQDatasets`
- `DYNAMODB_AUDIT_RUNS_TABLE` = `AuditIQAuditRuns`
- `COGNITO_USER_POOL_ID` = `$USER_POOL_ID`
- `COGNITO_APP_CLIENT_ID` = `$APP_CLIENT_ID`
- `BEDROCK_MODEL_ID` = `anthropic.claude-3-haiku-20240307-v1:0`
- `PORT` = `8000`

App Runner will provide a live HTTPS URL such as:
`https://abc123xyz.us-east-1.awsapprunner.com`

---

## 9. Frontend Deployment on AWS Amplify

### A. Configure Production Environment
In `frontend/`:
```bash
# Set production App Runner URL
echo "VITE_API_BASE_URL=https://your-app-runner-service.awsapprunner.com" > .env.production
echo "VITE_AWS_REGION=us-east-1" >> .env.production
echo "VITE_COGNITO_USER_POOL_ID=$USER_POOL_ID" >> .env.production
echo "VITE_COGNITO_APP_CLIENT_ID=$APP_CLIENT_ID" >> .env.production
```

### B. Build and Deploy
```bash
cd frontend
npm install
npm run build
```
Deploy the generated `frontend/dist/` directory via the **AWS Amplify Console** or Amplify CLI.

---

## 10. CORS Configuration

On the App Runner service, update `AUDITIQ_CORS_ORIGINS`:
```bash
AUDITIQ_CORS_ORIGINS=https://main.d1234example.amplifyapp.com,http://localhost:5173
```

---

## 11. End-to-End Verification Smoke Test

1. Navigate to your deployed Amplify URL.
2. Verify application header displays **AuditIQ Cloud (AWS Native)**.
3. Upload `data/transactions.csv` (or any customer transaction spreadsheet).
4. Verify file is written to S3 and metadata appears in DynamoDB.
5. In the Ask AuditIQ panel, enter:
   `"Why did expenses increase in Q3?"`
6. Observe the **Audit Trail** tab: verify Bedrock tool selection, safe Pandas execution, grounding verification, and trust score calculation.
7. Click **Export Audit Report (PDF)**: verify the report is stored in S3 and downloaded through the secure URL.
8. Refresh the browser: verify your past investigation appears in the **Recent Audit Investigations** dashboard and can be reopened with a single click.
