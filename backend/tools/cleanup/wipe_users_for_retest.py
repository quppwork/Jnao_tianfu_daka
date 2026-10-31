#!/usr/bin/env python3
"""清空 Jnao 家长/孩子账号与关联数据，便于服务器重新联调；可选清空 snapshot 并全量同步老库。

用法（生产 Docker）:
  docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \\
    python tools/wipe_users_for_retest.py -y

  # 清空 snapshot 后从老库全量重拉
  docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \\
    python tools/wipe_users_for_retest.py -y --clear-snapshot --resync-legacy

诊断某手机号/ openid:
  docker compose ... exec -T backend python -m tools.lookup_wx_member --phone 13800138000
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(BACKEND.parent / ".env.production", override=False)

from sqlalchemy import delete, func, select, text

from app.db.models import (
    ChildUser,
    DakaMember,
    GuideMessage,
    GuideSession,
    ParentChildBind,
    ParentWechatBind,
    QaMessage,
    QaSession,
    TalentAssessment,
    TalentAssessmentArchive,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
    TrainingWindow,
    UserSession,
    WxMemberSnapshot,
)
from app.db.session import get_database_url, get_session_factory, init_db
from app.services.wechat_auth_service import _sync_state_path, sync_wx_members_from_legacy

_WIPE_ORDER = (
    GuideMessage,
    GuideSession,
    QaMessage,
    QaSession,
    TrainingRecord,
    TrainingItem,
    TrainingPlan,
    TrainingWindow,
    UserSession,
    ParentChildBind,
    ParentWechatBind,
    DakaMember,
    TalentAssessmentArchive,
    TalentAssessment,
    ChildUser,
)


def _confirm(url: str, *, assume_yes: bool) -> None:
    print(f"目标库: {url}")
    if assume_yes or "127.0.0.1" in url or "localhost" in url:
        return
    ans = input("即将清空用户数据，输入 yes 继续: ").strip().lower()
    if ans != "yes":
        print("已取消")
        raise SystemExit(1)


def wipe_users(db, *, clear_snapshot: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    for model in _WIPE_ORDER:
        name = model.__tablename__
        counts[name] = db.scalar(select(func.count()).select_from(model)) or 0
        db.execute(delete(model))
    if clear_snapshot:
        counts["wx_member_snapshot"] = (
            db.scalar(select(func.count()).select_from(WxMemberSnapshot)) or 0
        )
        db.execute(delete(WxMemberSnapshot))
    db.commit()
    return counts


def reset_sync_state() -> None:
    path = _sync_state_path()
    try:
        if path.is_file():
            path.unlink()
            print(f"已删除同步游标: {path}")
    except OSError as e:
        print(f"[WARN] 删除同步游标失败: {e}")


def legacy_phone_without_openid_count() -> int | None:
    from app.db.legacy_session import get_legacy_engine

    engine = get_legacy_engine()
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS c FROM ys_wx_member
                    WHERE (openid IS NULL OR openid = '')
                      AND mobile IS NOT NULL AND mobile != ''
                    """
                )
            ).mappings().first()
            return int(row["c"]) if row else 0
    except Exception as e:
        print(f"[WARN] 老库统计失败: {e}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe Jnao users for retest")
    parser.add_argument("-y", action="store_true", help="跳过确认")
    parser.add_argument(
        "--clear-snapshot",
        action="store_true",
        help="同时清空 wx_member_snapshot（建议配合 --resync-legacy）",
    )
    parser.add_argument(
        "--resync-legacy",
        action="store_true",
        help="清空后全量同步老库 ys_wx_member → wx_member_snapshot",
    )
    parser.add_argument(
        "--reset-sync-cursor",
        action="store_true",
        help="删除 /app/data/wx_sync_state.json 增量游标",
    )
    args = parser.parse_args()

    url = get_database_url()
    _confirm(url, assume_yes=args.y)

    init_db()
    factory = get_session_factory()
    db = factory()
    try:
        counts = wipe_users(db, clear_snapshot=args.clear_snapshot)
    finally:
        db.close()

    print(f"[{datetime.now():%F %T}] 已清空用户相关数据:")
    for table, n in counts.items():
        print(f"  {table}: {n} 条")

    if args.reset_sync_cursor or args.clear_snapshot:
        reset_sync_state()

    legacy_skip = legacy_phone_without_openid_count()
    if legacy_skip is not None:
        print(
            f"\n老库「有手机号、无 openid」记录: {legacy_skip} 条"
            "（全量同步不会导入，仅支持浏览器短信注册/登录）"
        )

    if args.resync_legacy:
        db = factory()
        try:
            stats = sync_wx_members_from_legacy(db)
            db.commit()
            print(
                f"\n老库全量同步完成: 共 {stats['total']} 条, "
                f"有手机号 {stats['with_mobile']}, 无手机号 {stats['without_mobile']}"
            )
        except RuntimeError as e:
            print(f"[ERROR] 同步失败: {e}")
            return 1
        finally:
            db.close()

    from app.services.auth_service import ensure_admin_account

    db = factory()
    try:
        admin = ensure_admin_account(db)
        if admin:
            print(f"\n管理员已就绪: {admin.login_name} (id={admin.id})")
    finally:
        db.close()

    print("\n后续:")
    print("  1. 浏览器 localStorage.clear(); location.reload()")
    print("  2. 用 lookup_wx_member 抽查: python -m tools.lookup_wx_member --phone 手机号")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
