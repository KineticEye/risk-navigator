# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Build and Development
- `npm run build` - Compile TypeScript code
- `npm run watch` - Watch mode for TypeScript compilation
- `npm test` - Run tests using Jest

### AWS CDK Operations
- `npm run cdk` - Run CDK CLI commands
- `npm run deploy` - Deploy infrastructure to AWS (`cdk deploy`)
- `npm run destroy` - Destroy AWS infrastructure (`cdk destroy`)
- `npm run diff` - Show differences between deployed and local stack (`cdk diff`)

### Python Dependencies
- `pip install -r requirements.txt` - Install Python dependencies for Lambda functions

### Local Testing
- `python test_local.py` - Run local tests for Lambda functions

## Architecture Overview

This is a serverless document classification system built with AWS CDK (TypeScript) and Python Lambda functions. The system uses Google's Gemini AI to classify insurance documents.

### Key Components

**Infrastructure (TypeScript/CDK)**
- `src/infrastructure/app.ts` - CDK app entry point, configures environment and account
- `src/infrastructure/stacks/document-classifier-stack.ts` - Main infrastructure stack defining:
  - S3 bucket for document storage with versioning and lifecycle rules
  - Lambda function for document classification
  - API Gateway REST API with CORS configuration
  - IAM roles and policies

**Lambda Functions (Python)**
- `src/lambdas/api/classify_documents.py` - Main classification handler that:
  - Accepts base64-encoded files via API Gateway
  - Uploads files to S3 with organized folder structure
  - Uses Gemini AI to classify documents into 4 categories: Loss Run, ACORD form, Supplemental forms, Mod sheet
  - Returns classification results with S3 metadata

### Document Classification Categories
1. **Loss Run** - Loss history, claims data, loss statistics
2. **ACORD form** - Standard insurance forms (ACORD 25, ACORD 28, etc.)
3. **Supplemental forms** - Additional forms, endorsements, riders
4. **Mod sheet** - Experience modification worksheets, rating documents

### API Endpoints
- `POST /api/aarm/classify` - Document classification endpoint
- `GET /health` - Health check endpoint

### Environment Configuration
- Uses `CDK_ENV` environment variable for environment naming (defaults to "dev")
- Lambda requires `GEMINI_API_KEY` environment variable
- Infrastructure deploys to us-east-2 region with hardcoded account ID

### File Structure
```
src/
├── infrastructure/        # AWS CDK TypeScript code
│   ├── app.ts            # CDK app configuration
│   └── stacks/           # CDK stack definitions
└── lambdas/              # Python Lambda functions
    └── api/              # API Lambda handlers
```

### Dependencies
- **TypeScript/CDK**: aws-cdk-lib, constructs, typescript, jest
- **Python**: google-generativeai, boto3, requests, python-multipart

### Development Notes
- S3 bucket names include environment suffix for isolation
- Lambda functions have 60-second timeout and 512MB memory
- CloudWatch logs retained for 1 week
- S3 object versioning enabled with 30-day cleanup for old versions
- CORS enabled for all origins on API Gateway