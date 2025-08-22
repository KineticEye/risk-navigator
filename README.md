# Risk Navigator

**Serverless Backend Infrastructure for Document Processing and AI-Powered Classification**

## Overview

Risk Navigator is a cloud-native backend system built on AWS serverless architecture for processing and classifying insurance and risk management documents using AI. The system leverages AWS services for scalable, cost-effective document analysis workflows.

## Architecture

### Core Components

- **AWS Lambda**: Serverless compute for document processing and AI integration
- **Amazon S3**: Object storage for document uploads and classification results
- **API Gateway**: RESTful API endpoints for client interactions
- **Google Gemini AI**: Advanced language model for document classification

### Infrastructure as Code

The entire infrastructure is defined and deployed using **AWS CDK (Cloud Development Kit)** with TypeScript, ensuring:
- ✅ Reproducible deployments across environments
- ✅ Version-controlled infrastructure changes
- ✅ Automated resource provisioning and configuration
- ✅ Consistent security and IAM policies

## Features

### Document Classification Service
- **Multi-format Support**: Processes PDF, Excel, CSV, and text documents
- **AI-Powered Analysis**: Uses Google Gemini AI for intelligent document classification
- **File Picker Interface**: Browse and select existing documents from S3
- **Real-time Processing**: Immediate classification results via REST API

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/aarm/list-files` | POST | List available documents in S3 |
| `/api/aarm/classify` | POST | Classify selected documents |

### Document Categories

The system classifies insurance documents into four categories:
- **Loss Run** - Claims history and loss statistics
- **ACORD Form** - Standard insurance forms (ACORD 25, 28, etc.)
- **Supplemental Forms** - Additional forms, endorsements, riders
- **Mod Sheet** - Experience modification worksheets

## Deployment

### Prerequisites
- AWS Account with appropriate permissions
- AWS CLI configured
- Node.js and npm
- AWS CDK CLI (`npm install -g aws-cdk`)
- Google Gemini API key

### Environment Setup
```bash
# Install dependencies
npm install

# Bootstrap CDK (first time only)
cdk bootstrap

# Set environment variables
export GEMINI_API_KEY="your-gemini-api-key"
export CDK_ENV="dev"  # or "prod"
```

### Deploy Infrastructure
```bash
# Deploy to development environment
cdk deploy

# Deploy to production environment
CDK_ENV=prod cdk deploy
```

### Environment Configuration

The system supports multiple deployment environments:
- **Development** (`dev`): For testing and development
- **Production** (`prod`): For live workloads

Each environment maintains isolated resources and configurations.

## Usage

### File Processing Workflow

1. **List Available Files**
   ```bash
   POST /api/aarm/list-files
   Body: {"action": "list_files"}
   ```

2. **Classify Documents**
   ```bash
   POST /api/aarm/classify
   Body: {
     "action": "classify_existing",
     "s3_keys": ["document1.pdf", "document2.xlsx"]
   }
   ```

### Local Testing

A local testing framework is provided for development:
```bash
# Set up Python environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r src/lambdas/api/requirements.txt

# Run local tests
export GEMINI_API_KEY="your-api-key"
python test_lambda_local.py
```

## Monitoring and Observability

- **CloudWatch Logs**: Automatic logging for all Lambda executions
- **CloudWatch Metrics**: Performance and error tracking
- **AWS X-Ray**: Distributed tracing (when enabled)
- **CDK Outputs**: Important endpoint URLs and resource identifiers

## Security

- **IAM Roles**: Principle of least privilege for all AWS resources
- **S3 Bucket Policies**: Secure access controls for document storage
- **API Gateway**: CORS configuration for web client integration
- **Environment Variables**: Secure configuration management

## Cost Optimization

The serverless architecture provides:
- **Pay-per-use**: Only charged for actual compute time
- **Auto-scaling**: Handles varying workloads automatically
- **No idle costs**: Resources scale to zero when not in use
- **Efficient storage**: S3 for cost-effective document storage

## Development

### Project Structure
```
├── src/
│   ├── infrastructure/        # CDK infrastructure code
│   │   ├── stacks/           # CloudFormation stacks
│   │   └── app.ts            # CDK application entry point
│   └── lambdas/              # Lambda function source code
│       └── api/              # API Lambda functions
├── test_lambda_local.py      # Local testing script
└── README.md                 # This file
```

### Contributing

1. Make infrastructure changes in `src/infrastructure/`
2. Test locally using provided scripts
3. Deploy to development environment first
4. Validate functionality before production deployment

## Support

For issues or questions related to the infrastructure:
- Check CloudWatch Logs for execution details
- Review CDK deployment outputs for endpoint URLs
- Verify AWS credentials and permissions
- Ensure all environment variables are properly set
