"""首页引导对话 — 豆包 AI，解答 App 使用问题"""

from fastapi import APIRouter, Request

from app.core.logger import get_logger
from app.services.doubao_client import chat_completion, is_configured

logger = get_logger("guide")

router = APIRouter(prefix="/api/guide", tags=["guide"])


@router.get("/debug")
async def guide_debug():
    from config.loader import load_settings

    c = load_settings().get("doubao", {})
    return {
        "provider": "doubao",
        "model": c.get("model"),
        "key_ok": is_configured(),
        "base": c.get("api_base"),
    }


SYSTEM_PROMPT = """你是 JNAO 天赋成长平台的智能助手，你的职责是帮助用户了解和使用本平台。

平台有四大功能：
1. 天赋测试 — 回答35道选择题，AI分析你的天赋类型（学者/思者/赢者/德者/行者），生成专属报告含雷达图和情绪分析。
2. 今日训练 — 每日打卡训练，按等级解锁训练内容（视频+音频），完成后生成训练总结。
3. 知识答题 — 语音或文字提问，AI老师一对一个性化辅导（数学/语文/英语/科学）。
4. 成长里程碑 — 记录成长轨迹，获得荣誉徽章，分享精彩瞬间。

使用流程：先做天赋测试→确定等级→每日训练→知识答题→查看成长。

回答规则：
- 只回答平台使用相关的问题，引导用户使用上述功能
- 不提供具体训练内容、题目答案或用户个人数据
- 不知道的信息诚实说"这部分需要联系老师了解"
- 语气温暖亲切，像一位耐心的教育顾问
- 回答简洁，2-4句话即可
"""


@router.post("/chat")
async def guide_chat(request: Request):
    data = await request.json()
    msg = data.get("message", "")
    if not msg:
        return {"reply": "请输入问题。"}

    if not is_configured():
        return {"reply": "AI 服务未配置，请先设置豆包 API Key。"}

    reply = await chat_completion(system_prompt=SYSTEM_PROMPT, user_message=msg)
    if not reply:
        return {"reply": "抱歉，AI 暂时无法响应，请稍后再试。"}

    logger.info(f"Guide chat: {msg[:30]}... → {reply[:30]}...")
    return {"reply": reply}
