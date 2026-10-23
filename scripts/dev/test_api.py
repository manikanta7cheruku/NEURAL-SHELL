"""
Quick API Test Script - Run all endpoint tests
"""

import requests
import json

BASE = "http://localhost:7777/api"

def test(name, method, endpoint, data=None, expected_key=None):
    """Test an endpoint."""
    url = f"{BASE}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=5)
        elif method == "POST":
            r = requests.post(url, json=data, timeout=5)
        elif method == "PUT":
            r = requests.put(url, json=data, timeout=5)
        else:
            print(f"❓ {name}: Unknown method {method}")
            return
        
        if r.status_code == 200:
            result = r.json()
            if expected_key and expected_key in result:
                print(f"✅ {name}: OK ({expected_key}={result[expected_key]})")
            else:
                print(f"✅ {name}: OK")
        else:
            print(f"❌ {name}: HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"❌ {name}: Connection failed (is Seven running?)")
    except Exception as e:
        print(f"❌ {name}: {e}")

def main():
    print("\n" + "=" * 50)
    print("SEVEN API TESTS")
    print("=" * 50 + "\n")
    
    # Core
    test("Status", "GET", "/status", expected_key="mood")
    test("Version", "GET", "/version", expected_key="version")
    
    # License
    test("License Status", "GET", "/license/status", expected_key="tier")
    test("License Features", "GET", "/license/features")
    
    # Usage
    test("Usage Stats", "GET", "/usage/stats", expected_key="display")
    test("Usage History", "GET", "/usage/history")
    
    # Referral
    test("Referral Stats", "GET", "/referral/stats")
    
    # Memory
    test("Memory Stats", "GET", "/memory/stats")
    test("Memory Facts", "GET", "/memory/facts")
    
    # Config
    test("Config", "GET", "/config", expected_key="brain")
    
    # Voice
    test("Voice Words", "GET", "/voice-control/words")
    
    # Email
    test("Email Check", "GET", "/email/check")
    
    # Hardware
    test("Hardware", "GET", "/hardware", expected_key="gpu")
    
    # Chat
    test("Chat", "POST", "/chat", {"text": "Hello"}, expected_key="response")
    
    print("\n" + "=" * 50)
    print("TESTS COMPLETE")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    main()