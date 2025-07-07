#!/usr/bin/env python3
"""
Simple AWS Credentials Setup
"""

import os
import subprocess
import sys

def set_environment_credentials():
    """Set AWS credentials as environment variables"""
    
    print("🔧 Setting AWS Credentials")
    print("=" * 40)
    
    # Get credentials from user
    access_key = input("Enter your AWS Access Key ID: ").strip()
    secret_key = input("Enter your AWS Secret Access Key: ").strip()
    
    # Set environment variables
    os.environ['AWS_ACCESS_KEY_ID'] = access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
    os.environ['AWS_DEFAULT_REGION'] = 'ap-south-1'
    
    print("\n✅ Credentials set as environment variables")
    print("✅ Region set to ap-south-1 (Mumbai)")
    
    # Test if boto3 is available
    try:
        import boto3
        print("✅ boto3 is available")
        
        # Test Bedrock access
        print("\n🧪 Testing Bedrock access...")
        bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name='ap-south-1'
        )
        
        # Simple test
        test_body = '{"inputText": "test"}'
        response = bedrock.invoke_model(
            body=test_body,
            modelId="amazon.titan-embed-text-v2:0",
            accept="application/json",
            contentType="application/json"
        )
        
        print("✅ Bedrock access successful!")
        print("✅ You can now run: python process_documents.py")
        
    except ImportError:
        print("❌ boto3 not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "boto3"])
        print("✅ boto3 installed. Please run this script again.")
        
    except Exception as e:
        print(f"❌ Error testing Bedrock: {e}")
        print("Please check your credentials and Bedrock access")

def create_credentials_file():
    """Create AWS credentials file"""
    
    print("\n📁 Creating AWS credentials file...")
    
    # Get user home directory
    home_dir = os.path.expanduser("~")
    aws_dir = os.path.join(home_dir, ".aws")
    
    # Create .aws directory
    if not os.path.exists(aws_dir):
        os.makedirs(aws_dir)
        print(f"✅ Created directory: {aws_dir}")
    
    # Get credentials
    access_key = input("Enter your AWS Access Key ID: ").strip()
    secret_key = input("Enter your AWS Secret Access Key: ").strip()
    
    # Create credentials file
    credentials_path = os.path.join(aws_dir, "credentials")
    with open(credentials_path, 'w') as f:
        f.write(f"""[default]
aws_access_key_id = {access_key}
aws_secret_access_key = {secret_key}
region = ap-south-1
""")
    
    print(f"✅ Credentials saved to: {credentials_path}")
    print("✅ You can now run: python process_documents.py")

def main():
    """Main function"""
    print("🔍 AWS Credentials Setup")
    print("=" * 40)
    
    print("Choose an option:")
    print("1. Set credentials as environment variables (temporary)")
    print("2. Create AWS credentials file (permanent)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        set_environment_credentials()
    elif choice == "2":
        create_credentials_file()
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main() 