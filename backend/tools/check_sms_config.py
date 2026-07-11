#!/usr/bin/env python3
"""检查短信配置与阿里云连通性（生产排查用）

用法:
  docker exec jnao-daka-backend python tools/check_sms_config.py
  docker exec jnao-daka-backend python tools/check_sms_config.py --send-test 13900001111
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

if not os.getenv("DATABASE_URL"):
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_BACKEND, ".env"), override=False)
    _prod = os.path.join(_BACKEND, "..", ".env.production")
    if os.path.isfile(_prod):
        load_dotenv(_prod, override=False)

from app.core.cache import get_client
from app.services.sms_service import _aliyun_sms_credentials, _is_mock


def main() -> None:
    parser = argparse.ArgumentParser(description="检查 SMS 配置")
    parser.add_argument("--send-test", metavar="PHONE", help="向该号发送测试验证码（慎用）")
    args = parser.parse_args()

    provider = (os.getenv("SMS_PROVIDER") or "mock").strip().lower()
    ak, sk = _aliyun_sms_credentials()
    sign = (os.getenv("ALIYUN_SMS_SIGN_NAME") or "").strip()
    tpl = (os.getenv("ALIYUN_SMS_TEMPLATE_CODE") or "").strip()
    redis_ok = get_client() is not None

    out = {
        "sms_provider": provider,
        "is_mock": _is_mock(),
        "redis_ok": redis_ok,
        "aliyun_ak_set": bool(ak),
        "aliyun_sk_set": bool(sk),
        "sign_name": sign,
        "template_code": tpl,
        "hourly_ip_limit": os.getenv("SMS_HOURLY_PER_IP", "30"),
    }

    if provider == "aliyun":
        try:
            import alibabacloud_dysmsapi20170525  # noqa: F401

            out["sdk_installed"] = True
        except ImportError:
            out["sdk_installed"] = False

    print(json.dumps(out, ensure_ascii=False, indent=2))

    if args.send_test and provider == "aliyun" and not _is_mock():
        from app.services.sms_service import _dispatch_aliyun_sms

        _dispatch_aliyun_sms(args.send_test, "123456", "login")
        print(json.dumps({"send_test": args.send_test, "ok": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
