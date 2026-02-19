
import requests

url = "http://localhost:8000/api/v1/auth/login"
data = {"username": "sarah@sarcastic.ai", "password": "sarah123"}
print(f"Testing login to {url} with {data['username']}...")

try:
    resp = requests.post(url, data=data)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
