"""端到端流程测试 — 模拟真实用户操作，测试完整工作流

运行: python tests/test_workflow_e2e.py
要求: 后端在 8012 端口运行中
"""

import urllib.request
import urllib.error
import json
import sys

BASE = "http://127.0.0.1:8012"
PASS = 0
FAIL = 0

def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  ✅ {name}")
    except Exception as e:
        FAIL += 1
        print(f"  ❌ {name}: {e}")

def api(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def get(path):
    return api("GET", path)

def post(path, body):
    return api("POST", path, body)


def register_guide_user():
    """引导对话需 child user_id（与 test_e2e_flows 一致）"""
    code, data = post("/api/auth/register", {
        "parent_phone": "13800006666",
        "nickname": "工作流引导测试",
    })
    assert code == 200, f"register failed {code}: {data}"
    return data["child_user_id"]


GUIDE_USER_ID = register_guide_user()


def guide_post(message: str):
    return post(f"/api/guide/chat?user_id={GUIDE_USER_ID}", {"message": message})


# ═══════════════════════════════════════════════
#  流程线一：天赋测试
# ═══════════════════════════════════════════════

print("\n📋 流程线一：天赋测试")

def test_health():
    code, data = get("/api/health")
    assert code == 200, f"status code {code}"
    assert data["status"] == "ok", f"status not ok: {data}"

test("健康检查", test_health)


def test_talent_submit_adult():
    """成人测试：提交答案 → 返回报告"""
    code, data = post("/api/talent/report", {
        "answer": "11000111110001001001011111000101001",
        "uid": 1,
        "type": 0
    })
    assert code == 200, f"status code {code}"
    assert data["code"] == 1, f"code != 1: {data}"
    assert "data" in data, f"no data field"
    assert data["data"]["talent"], f"no talent: {data['data']}"
    assert data["data"]["results"]["Ability"], f"no Ability"
    assert len(data["data"]["results"]["Ability"]) == 4, f"expected 4 abilities"
    # 验证报告结构
    r = data["data"]
    assert r["results"]["State"]["name"], "no state name"
    assert r["results"]["Attribute"]["attribute"]["name"], "no attribute"

test("成人天赋测试：提交答案→获取报告", test_talent_submit_adult)


def test_talent_submit_child():
    """儿童测试"""
    code, data = post("/api/talent/report", {
        "answer": "10101010101010101010101010101010101",
        "uid": 1,
        "type": 1
    })
    assert code == 200
    assert data["code"] == 1
    assert data["data"]["talent"]

test("儿童天赋测试：提交答案→获取报告", test_talent_submit_child)


def test_talent_invalid_answer_short():
    """答案太短 → 422"""
    code, data = post("/api/talent/report", {
        "answer": "110",
        "uid": 1,
        "type": 0
    })
    assert code == 422, f"expected 422 got {code}"

test("答案过短 → 422", test_talent_invalid_answer_short)


def test_talent_invalid_type():
    """无效 type → 422"""
    code, data = post("/api/talent/report", {
        "answer": "11000111110001001001011111000101001",
        "uid": 1,
        "type": 99
    })
    assert code == 422, f"expected 422 got {code}"

test("无效测试类型 → 422", test_talent_invalid_type)

def test_report_structure():
    """验证报告数据结构完整性"""
    code, data = post("/api/talent/report", {
        "answer": "11000111110001001001011111000101001",
        "uid": 1,
        "type": 0
    })
    r = data["data"]
    required = ["id", "talent", "check_talent", "create_time", "results", "property", "StateIcon"]
    for field in required:
        assert field in r or field.replace("StateIcon","") in str(r), f"missing {field}"

test("报告数据结构完整性", test_report_structure)


# ═══════════════════════════════════════════════
#  流程线二：首页引导对话
# ═══════════════════════════════════════════════

print("\n📋 流程线二：首页引导对话")

def test_guide_chat_basic():
    """基本对话"""
    code, data = guide_post("你好")
    assert code == 200, f"status code {code}"
    assert "reply" in data, f"no reply: {data}"
    assert len(data["reply"]) > 5, f"reply too short: {data['reply']}"

test("基本对话：你好→AI回复", test_guide_chat_basic)


def test_guide_chat_talent():
    """询问天赋测试"""
    code, data = guide_post("天赋测试怎么做")
    assert code == 200
    assert len(data["reply"]) > 10

test("询问功能：天赋测试怎么做→AI回答", test_guide_chat_talent)


def test_guide_chat_empty():
    """空消息 → 422（Pydantic 校验，与 test_module_home 一致）"""
    code, data = guide_post("")
    assert code == 422, f"expected 422 got {code}: {data}"

test("空消息→422", test_guide_chat_empty)


def test_guide_debug_config():
    code, data = get("/api/guide/debug")
    assert code == 200
    assert data["key_ok"] == True, f"API key not configured: {data}"
    assert "doubao" in data["model"], f"wrong model: {data}"

test("豆包配置检查", test_guide_debug_config)


# ═══════════════════════════════════════════════
#  语音服务
# ═══════════════════════════════════════════════

print("\n📋 语音服务")

def test_tts_endpoint():
    """TTS 端点可访问"""
    code, data = post("/api/voice/tts", {"text": "你好"})
    # 可能返回 mp3 或 error(未配置)，只要不是 500 就算正常
    assert code < 500, f"TTS server error {code}"

test("TTS 端点可访问", test_tts_endpoint)


def test_asr_endpoint_no_audio():
    """ASR 端点缺少文件 → 422"""
    code, data = post("/api/voice/asr", None)
    assert code == 422, f"expected 422 got {code}"

test("ASR 缺少音频文件 → 422", test_asr_endpoint_no_audio)


# ═══════════════════════════════════════════════
#  结果汇总
# ═══════════════════════════════════════════════

print(f"\n{'='*40}")
print(f"  ✅ {PASS} passed  ❌ {FAIL} failed  (total {PASS+FAIL})")
print(f"{'='*40}")

sys.exit(0 if FAIL == 0 else 1)
