"""兼容门面 — 咨询 Agent 核已迁至 app.agents.consult.runner。

新代码请：from app.agents.consult.runner import generate_consult_reply
"""

from app.agents.consult.runner import generate_consult_reply

__all__ = ["generate_consult_reply"]
