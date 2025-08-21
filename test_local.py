#!/usr/bin/env python3
"""
Simple local test for the document classification Lambda function
"""

import json
import sys
import os

# Add the src directory to Python path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_hello_world():
    """
    Simple hello world test to verify the Lambda function loads correctly
    """
    print("🧪 Starting Hello World Test...")
    
    try:
        # Import our Lambda handler
        from lambdas.api.classify_documents import handler
        
        print("✅ Successfully imported Lambda handler")
        
        # Create a simple test event
        test_event = {
            'body': json.dumps({
                'files': [
                    {
                        'filename': 'test_document.pdf',
                        'content': 'SGVsbG8gV29ybGQ='  # Base64 encoded "Hello World"
                    }
                ]
            }),
            'headers': {
                'content-type': 'application/json'
            }
        }
        
        print("📝 Test event created")
        print(f"📄 Test event: {json.dumps(test_event, indent=2)}")
        
        # Call the handler
        print("🚀 Calling Lambda handler...")
        response = handler(test_event, None)
        
        print("✅ Handler executed successfully!")
        print(f"📤 Response: {json.dumps(response, indent=2)}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 DOCUMENT CLASSIFICATION - LOCAL TEST")
    print("=" * 50)
    
    success = test_hello_world()
    
    print("=" * 50)
    if success:
        print("🎉 Hello World test PASSED!")
    else:
        print("💥 Hello World test FAILED!")
    print("=" * 50) 