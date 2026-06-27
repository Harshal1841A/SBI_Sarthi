from locust import HttpUser, task, between
import uuid

class SarthiUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        self.session_id = str(uuid.uuid4())
        # The default api token from the env or the fallback
        self.headers = {"Authorization": "Bearer " + "sarthi-dev-token"}

    @task(3)
    def chat_message(self):
        payload = {
            "session_id": self.session_id,
            "message": "What is my account balance?",
            "language": "en",
            "channel": "chat"
        }
        self.client.post("/chat/message", json=payload, headers=self.headers)

    @task(1)
    def health_check(self):
        self.client.get("/health")
