# tests/test_health.py
import requests
import time

def test_health_up():
    # assumes service is running locally on port 8080 during test
    for _ in range(10):
        try:
            r = requests.get("http://127.0.0.1:8080/health", timeout=2)
            assert r.status_code == 200
            return
        except Exception:
            time.sleep(1)
    assert False, "health endpoint not responding"
