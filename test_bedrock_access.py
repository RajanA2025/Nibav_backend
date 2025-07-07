#!/usr/bin/env python3
"""
Test AWS Bedrock Model Access
"""

import boto3
import json
import os
from botocore.exceptions import NoCredentialsError, ClientError

def test_bedrock_access():
    """Test if Bedrock models are accessible"""
    
    print("🧪 Testing AWS Bedrock Access")
    print("=" * 50)
    
    # Check if credentials are available
    print("1. Checking AWS credentials...")
    
    # Try to get credentials from environment
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    
    if not access_key or not secret_key:
        print("❌ AWS credentials not found in environment variables")
        print("   Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False
    
    print("✅ AWS credentials found in environment")
    
    # Test Bedrock client creation
    print("\n2. Testing Bedrock client creation...")
    try:
        bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name='ap-south-1',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        print("✅ Bedrock client created successfully")
    except Exception as e:
        print(f"❌ Failed to create Bedrock client: {e}")
        return False
    
    # Test Titan Embeddings V2 model
    print("\n3. Testing Titan Embeddings V2 model...")
    try:
        test_body = json.dumps({"inputText": "Hello, this is a test message"})
        response = bedrock.invoke_model(
            body=test_body,
            modelId="amazon.titan-embed-text-v2:0",
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        embedding = response_body['embedding']
        
        print(f"✅ Titan Embeddings V2 working!")
        print(f"   Embedding dimension: {len(embedding)}")
        print(f"   First 5 values: {embedding[:5]}")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            print("❌ Access denied to Titan Embeddings V2")
            print("   Please check your Bedrock permissions")
        elif error_code == 'ValidationException':
            print("❌ Invalid model ID for Titan Embeddings V2")
        else:
            print(f"❌ AWS Error: {error_code}")
        return False
    except Exception as e:
        print(f"❌ Error testing Titan Embeddings V2: {e}")
        return False
    
    # Test Titan Text Lite model
    print("\n4. Testing Titan Text Lite model...")
    try:
        test_body = json.dumps({
            "inputText": "Hello, how are you?",
            "textGenerationConfig": {
                "maxTokenCount": 50,
                "stopSequences": [],
                "temperature": 0.7,
                "topP": 0.9
            }
        })
        
        response = bedrock.invoke_model(
            body=test_body,
            modelId="amazon.titan-text-lite-v1",
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        generated_text = response_body['results'][0]['outputText']
        
        print(f"✅ Titan Text Lite working!")
        print(f"   Generated text: {generated_text}")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            print("❌ Access denied to Titan Text Lite")
            print("   Please check your Bedrock permissions")
        elif error_code == 'ValidationException':
            print("❌ Invalid model ID for Titan Text Lite")
        else:
            print(f"❌ AWS Error: {error_code}")
        return False
    except Exception as e:
        print(f"❌ Error testing Titan Text Lite: {e}")
        return False
    
    # Test region access
    print("\n5. Testing region access...")
    try:
        bedrock_list = boto3.client('bedrock', region_name='ap-south-1')
        print("✅ Mumbai region (ap-south-1) accessible")
    except Exception as e:
        print(f"❌ Error accessing Mumbai region: {e}")
        return False
    
    print("\n🎉 All Bedrock tests passed!")
    print("✅ Your AWS Bedrock setup is working correctly")
    print("✅ You can now run: python process_documents.py")
    
    return True

def check_credentials_file():
    """Check if AWS credentials file exists"""
    print("\n📁 Checking for AWS credentials file...")
    
    # Check common locations
    possible_paths = [
        os.path.expanduser("~/.aws/credentials"),
        os.path.expanduser("~/.aws/config"),
        "C:\\Users\\%USERNAME%\\.aws\\credentials",
        "C:\\Users\\%USERNAME%\\.aws\\config"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Found credentials file: {path}")
            return True
    
    print("❌ No AWS credentials file found")
    return False

def main():
    """Main function"""
    print("🔍 AWS Bedrock Access Checker")
    print("=" * 50)
    
    # Check credentials file
    check_credentials_file()
    
    # Test Bedrock access
    success = test_bedrock_access()
    
    if not success:
        print("\n❌ Bedrock access failed!")
        print("\n🔧 Troubleshooting steps:")
        print("1. Ensure you have AWS credentials with Bedrock access")
        print("2. Check if Bedrock is available in ap-south-1 region")
        print("3. Verify your IAM permissions include Bedrock access")
        print("4. Try setting credentials manually:")
        print("   set AWS_ACCESS_KEY_ID=your_access_key")
        print("   set AWS_SECRET_ACCESS_KEY=your_secret_key")
        print("   set AWS_DEFAULT_REGION=ap-south-1")

if __name__ == "__main__":
    main() 