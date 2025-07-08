#!/usr/bin/env python3
"""
AWS Credentials Setup for Bedrock
"""

import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

def setup_aws_credentials():
    """Setup AWS credentials for Bedrock access"""
    
    print("🔧 AWS Credentials Setup for Bedrock")
    print("=" * 50)
    
    # Get credentials from user
    print("Please enter your AWS credentials:")
    access_key = input("AWS Access Key ID: ").strip()
    secret_key = input("AWS Secret Access Key: ").strip()
    
    # Set environment variables
    os.environ['AWS_ACCESS_KEY_ID'] = access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
    os.environ['AWS_DEFAULT_REGION'] = 'ap-south-1'
    
    print("\n✅ Credentials set as environment variables")
    
    # Test Bedrock access
    print("\n🧪 Testing Bedrock access...")
    try:
        bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name='ap-south-1',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # Test with a simple embedding request
        test_body = '{"inputText": "test"}'
        response = bedrock.invoke_model(
            body=test_body,
            modelId="amazon.titan-embed-text-v2:0",
            accept="application/json",
            contentType="application/json"
        )
        
        print("✅ Bedrock access successful!")
        print("✅ You can now run: python process_documents.py")
        
        return True
        
    except NoCredentialsError:
        print("❌ Invalid credentials provided")
        return False
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            print("❌ Access denied. Please check your Bedrock permissions")
        elif error_code == 'ValidationException':
            print("❌ Invalid model ID or region")
        else:
            print(f"❌ AWS Error: {error_code}")
        return False
    except Exception as e:
        print(f"❌ Error testing Bedrock: {e}")
        return False

def create_credentials_file():
    """Create AWS credentials file"""
    
    print("\n📁 Creating AWS credentials file...")
    
    # Create .aws directory
    aws_dir = os.path.expanduser("~/.aws")
    if not os.path.exists(aws_dir):
        os.makedirs(aws_dir)
    
    # Create credentials file
    credentials_path = os.path.join(aws_dir, "credentials")
    
    print("Please enter your AWS credentials for the credentials file:")
    access_key = input("AWS Access Key ID: ").strip()
    secret_key = input("AWS Secret Access Key: ").strip()
    
    with open(credentials_path, 'w') as f:
        f.write(f"""[default]
aws_access_key_id = {access_key}
aws_secret_access_key = {secret_key}
region = ap-south-1
""")
    
    print(f"✅ Credentials saved to: {credentials_path}")
    print("✅ You can now run: python process_documents.py")

if __name__ == "__main__":
    print("Choose an option:")
    print("1. Set credentials as environment variables (temporary)")
    print("2. Create AWS credentials file (permanent)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        setup_aws_credentials()
    elif choice == "2":
        create_credentials_file()
    else:
        print("Invalid choice") 