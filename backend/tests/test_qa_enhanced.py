import pytest
"""学科答疑增强 API — 画像 / 拍图 / RAG / 教练元数据"""

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def _tiny_png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


class TestQaLearnerProfile:
    def test_update_learner_profile(self, client: TestClient, child_with_assessment):
        uid = child_with_assessment
        res = client.put(
            f"/api/user/learner-profile?user_id={uid}",
            json={"age": 10, "grade": "四年级", "school_stage": "primary_high"},
        )
        assert res.status_code == 200
        profile = res.json()["profile_json"]
        assert profile["grade"] == "四年级"
        assert profile["age"] == 10


class TestQaImageUpload:
    def test_upload_image_local(self, client: TestClient, child_with_assessment):
        uid = child_with_assessment
        png = _tiny_png()
        res = client.post(
            f"/api/qa/upload-image?user_id={uid}",
            files={"file": ("q.png", io.BytesIO(png), "image/png")},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["image_id"]
        assert data["url"]

    def test_upload_rejects_svg(self, client: TestClient, child_with_assessment):
        uid = child_with_assessment
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        res = client.post(
            f"/api/qa/upload-image?user_id={uid}",
            files={"file": ("evil.svg", io.BytesIO(svg), "image/svg+xml")},
        )
        assert res.status_code == 400


class TestQaChatEnhanced:
    def test_chat_hides_internal_metadata(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        client.put(
            f"/api/user/learner-profile?user_id={uid}",
            json={"grade": "四年级", "age": 10},
        )
        res = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "分数加法怎么算？", "subject": "数学"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "coach_hint" not in data
        assert "mistake_pattern" not in data
        assert "rag_used" not in data
        assert "ocr_preview" not in data
        assert data["school_stage"] == "primary_high"
        assert data["talent_primary"] == "学者"

    def test_chat_with_image_id(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        png = _tiny_png()
        up = client.post(
            f"/api/qa/upload-image?user_id={uid}",
            files={"file": ("q.png", io.BytesIO(png), "image/png")},
        ).json()
        with patch(
            "app.agents.qa.runner.vision_chat_completion",
            new_callable=AsyncMock,
            return_value="【测试】识题：1+1=?",
        ) as vision_mock:
            res = client.post(
                f"/api/qa/chat?user_id={uid}",
                json={
                    "message": "请帮我看这道题",
                    "image_id": up["image_id"],
                    "subject": "数学",
                },
            )
        assert res.status_code == 200
        assert vision_mock.call_count >= 1
        assert "ocr_preview" not in res.json()

    def test_rag_context_injected(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        rag_reply = {
            "answer": "参考资料：先通分再相加",
            "sources": ["k12_math"],
            "source_refs": [],
        }
        with patch(
            "app.agents.qa.runner.rag_chat",
            new_callable=AsyncMock,
            return_value=rag_reply,
        ):
            res = client.post(
                f"/api/qa/chat?user_id={uid}",
                json={
                    "message": "四年级分数加法怎么引导孩子列式？",
                    "subject": "数学",
                    "use_rag": True,
                },
            )
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"]
        assert data["reply"]
        assert "rag_used" not in data
        assert "rag_sources" not in data
