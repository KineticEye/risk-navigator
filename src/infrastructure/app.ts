#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DocumentClassifierStack } from './stacks/document-classifier-stack.ts';

const app = new cdk.App();
const stackProps: cdk.StackProps = {
  env: {
    account: "381387290883",
    region: "us-east-2",
  },
};

let envName = "dev";
if (process.env.CDK_ENV) {
  envName = process.env.CDK_ENV;
}
const stack = new DocumentClassifierStack(app, `document-classifier-${envName}`, stackProps);