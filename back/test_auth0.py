#!/usr/bin/env python3

import requests
import json

def test_auth0_api():
    url = "http://localhost:8000/api/v1/users/auth0"
    
    # 테스트 데이터
    test_data = {
        "id": "test_user_123",
        "email": "test@example.com",
        "name": "Test User",
        "picture": "https://example.com/avatar.jpg",
        "email_verified": True,
        "given_name": "Test",
        "nickname": "testuser",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    
    # Authorization 헤더 없이 테스트 (인증 우회)
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=test_data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200 or response.status_code == 201:
            print("✅ API 호출 성공!")
        else:
            print("❌ API 호출 실패!")
            
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    test_auth0_api() 