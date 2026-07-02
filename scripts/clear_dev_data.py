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
    ParentChildBind,
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
        # FK 依赖顺序：先删子表，再删父表
        # 1. 最底层的子记录（无其他表依赖它们）
        db.execute(delete(TrainingRecord))      # FK→child_user, FK→training_plan
        db.execute(delete(TrainingItem))         # FK→training_plan
        db.execute(delete(QaMessage))            # FK→qa_session
        db.execute(delete(GuideMessage))         # FK→guide_session

        # 2. 中间层
        db.execute(delete(QaSession))            # 引用 child_user_id
        db.execute(delete(GuideSession))          # 引用 child_user_id
        db.execute(delete(TrainingPlan))          # FK→child_user
        db.execute(delete(TrainingWindow))        # 引用 child_user_id
        db.execute(delete(TalentAssessment))      # FK→child_user
        db.execute(delete(TalentAssessmentArchive))
        db.execute(delete(ParentChildBind))       # FK→child_user (parent_id, child_id)

        # 3. 根表
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
