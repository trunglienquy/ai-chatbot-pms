#!/usr/bin/env python3
"""
Test token info endpoint
"""

import requests
import json
from threading import Thread
import time
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def start_flask_app():
    """Start Flask app in background"""
    from app_chatbot_gemini import app
    app.run(host="0.0.0.0", port=5000, debug=False)

def test_token_endpoint():
    """Test token endpoint"""
    print("🧪 Testing Token Info Endpoint...")
    
    # Wait for server to start
    time.sleep(2)
    
    try:
        response = requests.get("http://localhost:5000/token/info")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Token info endpoint working!")
            print(json.dumps(data, indent=2))
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure Flask app is running.")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def main():
    print("🚀 Starting Flask App Test\n")
    
    # Start Flask app in background thread
    flask_thread = Thread(target=start_flask_app, daemon=True)
    flask_thread.start()
    
    # Test token endpoint
    test_token_endpoint()
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    main()
