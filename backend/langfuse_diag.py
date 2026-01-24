import os
import time
import requests
from langfuse import Langfuse
import json

# Load env via centralized config entrypoint (dotenv policy).
# Running `python backend/langfuse_diag.py` adds `backend/` to sys.path, so this works.
import config.settings as _settings  # noqa: F401

# 1. Check Env Vars
print("=== 1. Environment Variables ===")
host = os.getenv("LANGFUSE_HOST")
pk = os.getenv("LANGFUSE_PUBLIC_KEY")
sk = os.getenv("LANGFUSE_SECRET_KEY")
print(f"HOST: {host}")
print(f"PK: {pk}")
print(f"SK: {sk[:10]}...")

# 2. Check Server Connectivity
print("\n=== 2. Server Connectivity ===")
try:
    resp = requests.get(f"{host}/api/public/health")
    print(f"Health Check: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"❌ Failed to connect to server: {e}")
    exit(1)

# 3. Create Trace
print("\n=== 3. Create Trace ===")
langfuse = Langfuse()
trace = langfuse.trace(name="diagnostic_test_trace", user_id="diag_user")
print(f"Trace ID: {trace.id}")

span = trace.span(name="diag_span")
span.end()
trace.update(output="success")
langfuse.flush()
print("✅ Trace flushed to SDK")

# 4. Wait for processing
print("\n=== 4. Waiting for Ingestion (10s) ===")
time.sleep(10)

# 5. Verify via API
print("\n=== 5. Verify via API ===")
try:
    url = f"{host}/api/public/traces/{trace.id}"
    resp = requests.get(url, auth=(pk, sk))
    if resp.status_code == 200:
        print("✅ Trace FOUND in API!")
        data = resp.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"❌ Trace NOT FOUND in API. Status: {resp.status_code}")
        print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error checking API: {e}")
