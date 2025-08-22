// Imports , imports the necessary AWS CDK libraries for the document classifier stack
// cdk = core development kit, a library for building AWS infrastructure using code
// Construct = a class that represents a cloud resource in the CDK
// lambda = AWS service for running code in response to events
// apigateway = AWS service for creating and managing APIs
// s3 = AWS service for storing and retrieving objects
// iam = AWS service for managing users, groups, and roles
// logs = AWS service for monitoring and logging

// This file defines the DocumentClassifierStack, which is a stack for the document classifier service.
// It creates the necessary resources for the service, including the S3 bucket, the Lambda function, and the API Gateway.
// It also creates the necessary IAM roles and policies for the service.
// It also creates the necessary CloudWatch logs for the service.

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';

export interface DocumentClassifierStackProps extends cdk.StackProps {
  // Add any custom props here
  geminiApiKey?: string;
}

//extends the cdk.Stack class to create AWS CloudFormation Stack
//from the stack i will inherit account id, region,CloudFormation stack name? 
export class DocumentClassifierStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: DocumentClassifierStackProps) {
    super(scope, id, props);

    // S3 Bucket for document storage
    const documentsBucket = new s3.Bucket(this, 'DocumentsBucket', {
      // Will this bucket be common to all endpoints i define for risk navigator?
      bucketName: `risk-navigator-documents-${process.env.CDK_ENV || "dev"}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      //should i be using lifecycle rules, and deleting the old versions?
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
      ],
    });

    // IAM Role for Lambda
    //IAM role is a way to manage permissions for the lambda function
    //Should i be doing this for all my lambdas?
    //I am assuming that the lambda role is a way to manage permissions for the lambda function
    const lambdaRole = new iam.Role(this, 'DocumentClassifierRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Add S3 permissions
    documentsBucket.grantReadWrite(lambdaRole);

    // Document Classification Lambda
    //This lambda function is the main function that will be used to classify the documents using the Gemini AI model
    //It contains the code for the lambda function, the runtime, the handler, the code, the role, the timeout, the memory size, the environment variables, and the log retention
    const classificationLambda = new lambda.Function(this, 'DocumentClassifier', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'classify_documents.handler',
      code: lambda.Code.fromAsset('src/lambdas/api'),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
      environment: {
        S3_BUCKET: documentsBucket.bucketName,
        //I am assuming that the gemini api key is stored in the environment variables and will be passed to the lambda function?
        GEMINI_API_KEY: process.env.GEMINI_API_KEY || '',
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // API Gateway
    //This is a REST API Gateway that will be used to classify the documents using the Gemini AI model
    //It contains the API name, the description, the default CORS preflight options, and the API resources and methods
    const api = new apigateway.RestApi(this, `DocumentClassifierAPI-${process.env.CDK_ENV || "dev"}`, {
      restApiName: 'Document Classifier API',
      description: 'API for classifying insurance documents using Gemini AI',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type'],
      },
    });

    // API Resources and Methods
    //Adds POST request and connects to the classification lambda function
    // /api/aarm/classify
    const classifyResource = api.root.addResource('api').addResource('aarm').addResource('classify');
    
    classifyResource.addMethod('POST', new apigateway.LambdaIntegration(classificationLambda));

    // Health check endpoint
    //Adds GET request and connects to the health check lambda function
    // /health
    //{status: 'healthy'}
    const healthResource = api.root.addResource('health');
    healthResource.addMethod('GET', new apigateway.LambdaIntegration(
      new lambda.Function(this, 'HealthCheck', {
        runtime: lambda.Runtime.PYTHON_3_11,
        handler: 'index.handler',
        code: lambda.Code.fromInline(`
import json

def handler(event, context):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'status': 'healthy',
            'service': 'document-classifier-api'
        })
    }
        `),
        timeout: cdk.Duration.seconds(10),
      })
    ));

    // Outputs
    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      //This is the base URL of the API Gateway
        value: api.url,
      description: 'API Gateway URL',
    });

    new cdk.CfnOutput(this, 'ClassifyEndpoint', {
        //The full URL of the classify endpoint
      value: `${api.url}api/aarm/classify`,
      description: 'Document classification endpoint',
    });

    new cdk.CfnOutput(this, 'DocumentsBucketName', {
      //This is the name of the S3 bucket for document storage
      value: documentsBucket.bucketName,
      description: 'S3 Bucket for document storage',
    });
  }
} 