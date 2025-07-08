#!/usr/bin/env python3
"""
Test script to debug authentication issues
"""

import requests
import time
import json

# Configuration
BASE_URL = "http://localhost:8000"  # Change if your server runs on different port

def test_login(email, password):
    """Test login functionality"""
    print(f"🔐 Testing login for {email}...")
    
    try:
        response = requests.post(f"{BASE_URL}/admin/login", data={
            "email": email,
            "password": password
        })
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Login successful: {data}")
            return True
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False

def test_session_status():
    """Test session status endpoint"""
    print("📊 Checking session status...")
    
    try:
        response = requests.get(f"{BASE_URL}/admin/session-status")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Session status: {json.dumps(data, indent=2)}")
            return data
        else:
            print(f"❌ Session status failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Session status error: {e}")
        return None

def test_authenticated_endpoint():
    """Test an authenticated endpoint"""
    print("🔒 Testing authenticated endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/admin/files")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Authenticated endpoint works: {data}")
            return True
        else:
            print(f"❌ Authenticated endpoint failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Authenticated endpoint error: {e}")
        return False

def test_session_refresh():
    """Test session refresh"""
    print("🔄 Testing session refresh...")
    
    try:
        response = requests.post(f"{BASE_URL}/admin/refresh-session")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Session refreshed: {data}")
            return True
        else:
            print(f"❌ Session refresh failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Session refresh error: {e}")
        return False

def monitor_session_duration():
    """Monitor session for a period of time"""
    print("⏰ Monitoring session for 5 minutes...")
    
    start_time = time.time()
    check_interval = 30  # Check every 30 seconds
    
    while time.time() - start_time < 300:  # 5 minutes
        print(f"\n--- Check at {time.strftime('%H:%M:%S')} ---")
        
        status = test_session_status()
        if status and status.get("authenticated"):
            time_remaining = status.get("time_remaining_minutes", 0)
            print(f"⏳ Time remaining: {time_remaining:.1f} minutes")
            
            # Test authenticated endpoint
            test_authenticated_endpoint()
        else:
            print("❌ Session expired or not authenticated")
            break
        
        time.sleep(check_interval)
    
    print("\n🏁 Session monitoring completed")

def main():
    """Main test function"""
    print("🧪 Authentication Test Suite")
    print("=" * 50)
    
    # Test credentials (replace with actual credentials)
    email = "admin@example.com"  # Replace with actual email
    password = "admin123"        # Replace with actual password
    
    # Step 1: Test login
    if not test_login(email, password):
        print("❌ Cannot proceed without successful login")
        return
    
    # Step 2: Check initial session status
    test_session_status()
    
    # Step 3: Test authenticated endpoint
    test_authenticated_endpoint()
    
    # Step 4: Test session refresh
    test_session_refresh()
    
    # Step 5: Monitor session (optional)
    print("\n" + "=" * 50)
    choice = input("Do you want to monitor session for 5 minutes? (y/n): ").lower()
    if choice.startswith('y'):
        monitor_session_duration()
    
    print("\n✅ Authentication test completed!")

if __name__ == "__main__":
    main() 