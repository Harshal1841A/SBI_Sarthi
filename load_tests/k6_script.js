import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 50,
  duration: '30s',
};

const BASE_URL = 'http://localhost:8000';
const TOKEN = 'sarthi-dev-token'; // Replace with actual token

export default function () {
  const payload = JSON.stringify({
    session_id: `k6-session-${__VU}-${__ITER}`,
    message: 'What is the interest rate for a home loan?',
    language: 'en',
    channel: 'chat'
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TOKEN}`,
    },
  };

  const res = http.post(`${BASE_URL}/chat/message`, payload, params);
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'has response': (r) => r.json('response') !== undefined,
  });

  sleep(1);
}
