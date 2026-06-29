#!/usr/bin/env python3
"""清空本地开发库中的学员与训练/测评数据（保留内容目录等静态数据）"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from dotenv import load_dotenv

load_dotenv(".env", override=True)

from sqlalchemy import delete, text

from app.db.models import (
    ChildUser,
    GuideMessage,
    GuideSession,
    QaMessage,
    QaSession,
    TalentAssessment,
    TalentAssessmentArchive,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
    TrainingWindow,
)
from app.db.session import get_session_factory, init_db


def main() -> None:
    init_db()
    db = get_session_factory()()
    try:
        db.execute(delete(TrainingRecord))
        db.execute(delete(TrainingItem))
        db.execute(delete(TrainingPlan))
        db.execute(delete(TrainingWindow))
        db.execute(delete(TalentAssessment))
        db.execute(delete(TalentAssessmentArchive))
        db.execute(delete(QaMessage))
        db.execute(delete(QaSession))
        db.execute(delete(GuideMessage))
        db.execute(delete(GuideSession))
        db.execute(delete(ChildUser))
        db.commit()
        print("OK: 已清空学员、训练、测评、答疑与引导会话数据")
        print(f"DATABASE_URL={os.environ.get('DATABASE_URL', '')}")
    except Exception as e:
        db.rollback()
        print(f"FAIL: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
