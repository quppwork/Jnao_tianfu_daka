"""P0：kb_registry + knowledge/chat SSE 解析测试。"""

import json

from app.services.bailian.knowledge_chat import parse_knowledge_chat_sse
from app.services.kb_registry import load_kb_registry


def test_kb_registry_loads_two_sources():
    reg = load_kb_registry()
    assert len(reg.sources) >= 2
    video = reg.get("video_practice")
    doc = reg.get("talent_doc")
    assert video and video.aid.startswith("aid-")
    assert doc and doc.index_id == "x1micrdmjq"
    assert "开口窍" in video.tags


def test_parse_knowledge_chat_sse_generating_only():
    lines = [
        'data: {"request_id":"r1","output":{"choices":[{"message":{"role":"assistant","content":"规划思考","extra":{"group":"planning","step":"planning"}}}]}}',
        'data: {"output":{"choices":[{"message":{"role":"assistant","content":"开口窍可以从","extra":{"group":"generating","step":"generating"}}}]}}',
        'data: {"output":{"choices":[{"message":{"role":"assistant","content":"慢到快练起。","extra":{"group":"generating","step":"generating","step_change":"generation_end"}}}]}}',
    ]
    parsed = parse_knowledge_chat_sse(lines)
    assert parsed["reply"] == "开口窍可以从慢到快练起。"
    assert "规划" not in parsed["reply"]
    assert parsed["planning_text"] == "规划思考"


def test_parse_knowledge_chat_sse_tool_docs():
    docs_payload = {
        "docs": [
            {
                "text": "训练视频切片",
                "score": 0.9,
                "metadata": {"doc_name": "开口窍的训练视频"},
            }
        ]
    }
    line = json.dumps(
        {
            "output": {
                "choices": [
                    {
                        "message": {
                            "role": "tool",
                            "content": "检索完成",
                            "additional_kwargs": {"extra_json": docs_payload},
                            "extra": {"step": "tool_calling", "step_change": "tool_return"},
                        }
                    }
                ]
            }
        },
        ensure_ascii=False,
    )
    parsed = parse_knowledge_chat_sse([f"data: {line}"])
    assert len(parsed["retrieved_docs"]) == 1
    assert parsed["retrieved_docs"][0].doc_name == "开口窍的训练视频"
