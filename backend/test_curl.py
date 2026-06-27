import requests

url = "http://localhost:8000/chat/message"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 8604aead39cd66840cd2ca31b62a9ec8080284544a84ebdb91dfd5aff79f6448"}
data = {
    "session_id": "test_new_123",
    "message": "hi",
    "language": "en",
    "channel": "chat"
}
response = requests.post(url, json=data, headers=headers)
print(response.status_code)
print(response.text)

