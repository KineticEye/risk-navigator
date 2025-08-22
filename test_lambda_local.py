#!/usr/bin/env python3
"""
Local Lambda Testing Script
Test your Lambda function directly without SAM or AWS deployment
"""

import json
import os
import sys
from datetime import datetime

#Add the Lambda source to Python path
sys.path.insert(0, 'src/lambdas/api')

#Set environment variables for testing
os.environ['UPLOADS_BUCKET'] = 'risk-navigator-documents-dev'
os.environ['RESULTS_BUCKET'] = 'risk-navigator-documents-dev'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-2'

#Check for Gemini API key
if not os.environ.get('GEMINI_API_KEY'):
    print("⚠️  Please set your GEMINI_API_KEY environment variable:")
    print("export GEMINI_API_KEY='your-actual-api-key'")
    print("Then run this script again.")
    exit(1)

# Import your Lambda function
try:
    from classify_documents import handler
    print("✅ Successfully imported Lambda function")
except ImportError as e:
    print(f"❌ Error importing Lambda function: {e}")
    print("Make sure you're running this from the project root directory")
    exit(1)

def test_list_files():
    """Test listing files in S3"""
    print("\n🔍 Testing: List Files")
    
    event = {
        'body': json.dumps({
            'action': 'list_files',
            'prefix': ''
        })
    }
    context = {}
    
    try:
        response = handler(event, context)
        print(f"Status Code: {response['statusCode']}")
        
        if response['statusCode'] == 200:
            body = json.loads(response['body'])
            if 'files' in body:
                print(f"✅ Found {len(body['files'])} files in bucket:")
                for file_info in body['files'][:5]:  # Show first 5 files
                    print(f"   📄 {file_info['filename']} ({file_info['size']} bytes)")
                if len(body['files']) > 5:
                    print(f"   ... and {len(body['files']) - 5} more files")
            else:
                print("⚠️  No files found or error in response")
        else:
            print(f"❌ Error response: {response.get('body', 'No error message')}")
            
    except Exception as e:
        print(f"❌ Exception during test: {str(e)}")

def test_classify_existing_files():
    """Test classifying existing files"""
    print("\n🎯 Testing: Classify Existing Files")
    
    # Test with a few of your insurance documents
    test_files = [
        "Buzz LRs 2023-24.pdf",
        "BUZZ - LOSS RUNS 2024-25.pdf",
        "BUZZ LLC - EMOD 2025.pdf"
    ]
    
    event = {
        'body': json.dumps({
            'action': 'classify_existing',
            's3_keys': test_files
        })
    }
    context = {}
    
    try:
        print(f"🔄 Classifying {len(test_files)} files...")
        response = handler(event, context)
        print(f"Status Code: {response['statusCode']}")
        
        if response['statusCode'] == 200:
            body = json.loads(response['body'])
            if 'data' in body and 'classifications' in body['data']:
                classifications = body['data']['classifications']
                print(f"✅ Successfully classified {len(classifications)} files:")
                
                for result in classifications:
                    filename = result.get('filename', 'Unknown')
                    classification = result.get('classification', 'Unknown')
                    error = result.get('error')
                    
                    if error:
                        print(f"   ❌ {filename}: ERROR - {error}")
                    else:
                        print(f"   ✅ {filename}: {classification}")
            else:
                print("⚠️  No classifications found in response")
        else:
            print(f"❌ Error response: {response.get('body', 'No error message')}")
            
    except Exception as e:
        print(f"❌ Exception during test: {str(e)}")

def main():
    """Run all tests"""
    print("🚀 Starting Local Lambda Tests")
    print(f"📅 Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🪣 Target bucket: {os.environ.get('UPLOADS_BUCKET')}")
    print("=" * 60)
    
    # Run tests
    test_list_files()
    test_classify_existing_files()
    
    print("\n" + "=" * 60)
    print("🎉 Local testing complete!")
    print("\n💡 Tips:")
    print("   • If tests pass, your Lambda is ready for deployment")
    print("   • If S3 access fails, check your AWS credentials")
    print("   • If Gemini fails, verify your GEMINI_API_KEY")

if __name__ == "__main__":
    main()