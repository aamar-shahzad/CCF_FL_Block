#!/usr/bin/env python3
"""
CCF API Test Script
Tests all API endpoints to verify connectivity
"""

import requests
import json
import sys
import time

# Configuration
CCF_BASE_URL = "http://localhost:8000"
PROXY_BASE_URL = "http://localhost:5000"

def test_endpoint(url, method="GET", data=None, headers=None, description=""):
    """Test a single endpoint"""
    print(f"\n🔍 Testing: {description}")
    print(f"   URL: {url}")
    print(f"   Method: {method}")
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=10)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers, timeout=10)
        else:
            print("   ❌ Unsupported method")
            return False
            
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ Success")
            try:
                result = response.json()
                print(f"   Response: {json.dumps(result, indent=2)}")
            except:
                print(f"   Response: {response.text[:200]}...")
            return True
        else:
            print(f"   ❌ Failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("   ❌ Connection Error: Service not running")
        return False
    except requests.exceptions.Timeout:
        print("   ❌ Timeout: Request took too long")
        return False
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False

def main():
    print("🚀 CCF API Connectivity Test")
    print("=" * 50)
    
    # Test 1: Proxy server health
    print("\n1️⃣ Testing Proxy Server")
    proxy_health = test_endpoint(
        f"{PROXY_BASE_URL}/api/health",
        description="Proxy Server Health Check"
    )
    
    # Test 2: CCF backend direct access
    print("\n2️⃣ Testing CCF Backend (Direct)")
    ccf_direct = test_endpoint(
        f"{CCF_BASE_URL}/user/add",
        method="GET",
        description="CCF Backend Direct Access"
    )
    
    # Test 3: User add (no auth required)
    print("\n3️⃣ Testing User Add")
    user_add = test_endpoint(
        f"{CCF_BASE_URL}/user/add",
        method="POST",
        data={"msg": "Test user from Python script"},
        headers={"Content-Type": "application/json"},
        description="User Add (No Auth Required)"
    )
    
    # Test 4: Model upload (no auth required)
    print("\n4️⃣ Testing Model Upload")
    model_upload = test_endpoint(
        f"{CCF_BASE_URL}/model/intial_model",
        method="POST",
        data={
            "global_model": {
                "model_name": "test_model",
                "model_data": {"layers": [{"weights": [0.1, 0.2, 0.3]}]}
            }
        },
        headers={"Content-Type": "application/json"},
        description="Model Upload (No Auth Required)"
    )
    
    # Test 5: Model download (requires auth)
    print("\n5️⃣ Testing Model Download (Requires Auth)")
    model_download = test_endpoint(
        f"{CCF_BASE_URL}/model/download/global?model_id=0",
        method="GET",
        description="Model Download (Auth Required - Will likely fail)"
    )
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    
    tests = [
        ("Proxy Server", proxy_health),
        ("CCF Backend Direct", ccf_direct),
        ("User Add", user_add),
        ("Model Upload", model_upload),
        ("Model Download (Auth)", model_download)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your API is working correctly.")
    elif passed >= 3:
        print("⚠️  Some tests passed. Check the failed tests above.")
        print("💡 For auth-required endpoints, you need to configure certificates.")
    else:
        print("❌ Most tests failed. Check if your servers are running.")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure CCF backend is running: ./build/app")
        print("2. Make sure proxy server is running: python3 proxy_server.py")
        print("3. Check if ports 8000 and 5000 are available")
        print("4. Run the debug test page: http://localhost:8080/debug_test.html")

if __name__ == "__main__":
    main() 