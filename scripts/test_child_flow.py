"""Test the child test flow end-to-end."""
import json
import urllib.request
import sys
sys.stdout.reconfigure(encoding="utf-8")

def api(method, path, data=None):
    url = f"http://127.0.0.1:8011{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={"Content-Type": "application/json"} if body else {})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()}

# Step 1: Create session
r = api("POST", "/api/talent/session", {})
d = r["data"]
sid = d["session_id"]
print(f"1. CREATE: sid={sid}, phase={d['phase']}, choices={d['choices']}")

# Step 2: Choose child test
r = api("POST", f"/api/talent/session/{sid}/action", {"choice": "孩子测试"})
d = r["data"]
print(f"2. 孩子测试: phase={d['phase']}, notice={d['notice']}, next_phase={d['next_phase']}")

# Step 3: Under 18
r = api("POST", f"/api/talent/session/{sid}/action", {"choice": "未满18岁"})
d = r["data"]
print(f"3. 未满18岁: phase={d['phase']}, notice={d['notice']!r}, next_phase={d['next_phase']}, next_choices={d['next_choices']}")

# Step 4: Ready to start
r = api("POST", f"/api/talent/session/{sid}/action", {"choice": "准备好了，开始吧"})
d = r["data"]
q = d.get("current_question")
if q:
    print(f"4. Start: phase={d['phase']}, test_type={d['test_type']}, q#{q['index']}: {q['text'][:60]}")
else:
    print(f"4. Start: phase={d['phase']}, test_type={d['test_type']}, NO QUESTION, error={d.get('error')}")
    print(f"   Full: {json.dumps(d, ensure_ascii=False, indent=2)[:500]}")
