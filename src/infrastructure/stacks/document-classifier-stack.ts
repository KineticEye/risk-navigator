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
import { Platform } from 'aws-cdk-lib/aws-ecr-assets';

export interface DocumentClassifierStackProps extends cdk.StackProps {
  // Add any custom props here
}

//extends the cdk.Stack class to create AWS CloudFormation Stack
//from the stack i will inherit account id, region,CloudFormation stack name? 
export class DocumentClassifierStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: DocumentClassifierStackProps) {
    super(scope, id, props);

    // Use existing S3 bucket for both uploads and results
    const documentsBucket = s3.Bucket.fromBucketName(
      this, 
      'ExistingDocumentsBucket', 
      'risk-navigator-documents-dev'
    );

    // IAM Role for Lambda
    //IAM role is a way to manage permissions for the lambda function
    //Basic Lambda functionality, i am assuming that the lambda role is a way to manage permissions for the lambda function
    const lambdaRole = new iam.Role(this, 'DocumentClassifierRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Add S3 read permissions (no write permissions needed)
    documentsBucket.grantRead(lambdaRole);

    // Document Classification Lambda
    //This lambda function is the main function that will be used to classify the documents using the Gemini AI model
    //Using Docker container to handle unlimited dependencies
    //Secrets manager is a way to store and manage secrets for the lambda function
    //put gemini api key in secrets manager and access it in the lambda function
    // to be done through console or via CLI
    // parameter store
    // environments.ts file in config in user-api
    const classificationLambda = new lambda.DockerImageFunction(this, 'DocumentClassifier', {
      code: lambda.DockerImageCode.fromImageAsset('src/lambdas/api', {
        platform: Platform.LINUX_AMD64,  // Explicit architecture for Lambda compatibility
      }),
      architecture: lambda.Architecture.X86_64,  // Match the platform
      role: lambdaRole,
      timeout: cdk.Duration.seconds(300),
      memorySize: 1024,
      environment: {
        UPLOADS_BUCKET: documentsBucket.bucketName,
        RESULTS_BUCKET: documentsBucket.bucketName,
        GEMINI_API_KEY: process.env.GEMINI_API_KEY || '',
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // API Gateway
    //This is a REST API Gateway that will be used to classify the documents using the Gemini AI model
    //It contains the API name, the description, the default CORS preflight options, and the API resources and methods
    const api = new apigateway.RestApi(this, 'DocumentClassifierAPI', {
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
    const apiResource = api.root.addResource('api');
    const aarmResource = apiResource.addResource('aarm');
    
    const classifyResource = aarmResource.addResource('classify');
    classifyResource.addMethod('POST', new apigateway.LambdaIntegration(classificationLambda));

    // Add list files endpoint
    const listFilesResource = aarmResource.addResource('list-files');
    listFilesResource.addMethod('POST', new apigateway.LambdaIntegration(classificationLambda));

    // Outputs
    new cdk.CfnOutput(this, 'DocumentsBucketName', {
      value: documentsBucket.bucketName,
      description: 'S3 Bucket for documents (existing bucket)',
    });

    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: api.url,
      description: 'API Gateway URL',
    });

    new cdk.CfnOutput(this, 'ClassifyEndpoint', {
      value: `${api.url}api/aarm/classify`,
      description: 'Document classification endpoint',
    });

    new cdk.CfnOutput(this, 'ListFilesEndpoint', {
      value: `${api.url}api/aarm/list-files`,
      description: 'List S3 files endpoint',
    });

    new cdk.CfnOutput(this, 'UsageInstructions', {
      value: 'Use list-files endpoint to see available files, then classify-existing to process them',
      description: 'How to use the file picker',
    });
  }
} 

//Store the response in a S3 bucket(*)
//Splitting the classifier stack , look into user-api stack for reference(*)
//We need to have new files in the lib directory which setup the stack and the resources(infrastructure)
//Define Authorizer lambda in the api gateway , look into user-api stack for reference(*)