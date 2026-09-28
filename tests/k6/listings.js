import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5,
  duration: '30s',
  thresholds: { http_req_duration: ['p(95)<500'] },
};

export default function () {
  const base = __ENV.BASE_URL || 'http://localhost:8000';
  const response = http.get(`${base}/list_os/`, { redirects: 0 });
  check(response, { 'lista responde': (r) => [200, 302].includes(r.status) });
  sleep(1);
}
