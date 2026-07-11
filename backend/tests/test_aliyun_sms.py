"""阿里云短信发送单元测试"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services import sms_service

# SDK 未安装时跳过需要 mock SDK 的测试
_sms_sdk_installed = False
try:
    import alibabacloud_dysmsapi20170525  # noqa: F401
    _sms_sdk_installed = True
except ImportError:
    pass

requires_sms_sdk = pytest.mark.skipif(
    not _sms_sdk_installed,
    reason="阿里云短信 SDK 未安装（alibabacloud_dysmsapi20170525）",
)


def test_aliyun_credentials_fallback_to_oss(monkeypatch):
    monkeypatch.delenv("ALIYUN_SMS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("ALIYUN_SMS_ACCESS_KEY_SECRET", raising=False)
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "oss-ak")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "oss-sk")
    assert sms_service._aliyun_sms_credentials() == ("oss-ak", "oss-sk")


def test_aliyun_dispatch_missing_config(monkeypatch):
    monkeypatch.setenv("ALIYUN_SMS_ACCESS_KEY_ID", "")
    monkeypatch.setenv("ALIYUN_SMS_ACCESS_KEY_SECRET", "")
    monkeypatch.delenv("OSS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("OSS_ACCESS_KEY_SECRET", raising=False)
    monkeypatch.setenv("ALIYUN_SMS_SIGN_NAME", "杭州劲脑软件开发")
    monkeypatch.setenv("ALIYUN_SMS_TEMPLATE_CODE", "SMS_241225115")

    with pytest.raises(HTTPException) as exc:
        sms_service._dispatch_aliyun_sms("13900001111", "123456", "login")
    assert exc.value.status_code == 503


@requires_sms_sdk
@patch("alibabacloud_dysmsapi20170525.client.Client")
def test_aliyun_dispatch_success(mock_client_cls, monkeypatch):
    monkeypatch.setenv("ALIYUN_SMS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("ALIYUN_SMS_ACCESS_KEY_SECRET", "sk")
    monkeypatch.setenv("ALIYUN_SMS_SIGN_NAME", "杭州劲脑软件开发")
    monkeypatch.setenv("ALIYUN_SMS_TEMPLATE_CODE", "SMS_241225115")

    mock_client = MagicMock()
    mock_client.send_sms.return_value = SimpleNamespace(
        body=SimpleNamespace(code="OK", message="OK", biz_id="biz-1")
    )
    mock_client_cls.return_value = mock_client

    sms_service._dispatch_aliyun_sms("13900001111", "123456", "login")

    mock_client.send_sms.assert_called_once()
    req = mock_client.send_sms.call_args[0][0]
    assert req.phone_numbers == "13900001111"
    assert req.sign_name == "杭州劲脑软件开发"
    assert req.template_code == "SMS_241225115"
    assert req.template_param == '{"code": "123456"}'


@requires_sms_sdk
@patch("alibabacloud_dysmsapi20170525.client.Client")
def test_aliyun_dispatch_api_error(mock_client_cls, monkeypatch):
    monkeypatch.setenv("ALIYUN_SMS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("ALIYUN_SMS_ACCESS_KEY_SECRET", "sk")
    monkeypatch.setenv("ALIYUN_SMS_SIGN_NAME", "杭州劲脑软件开发")
    monkeypatch.setenv("ALIYUN_SMS_TEMPLATE_CODE", "SMS_241225115")

    mock_client = MagicMock()
    mock_client.send_sms.return_value = SimpleNamespace(
        body=SimpleNamespace(code="isv.BUSINESS_LIMIT_CONTROL", message="limit")
    )
    mock_client_cls.return_value = mock_client

    with pytest.raises(HTTPException) as exc:
        sms_service._dispatch_aliyun_sms("13900001111", "123456", "register")
    assert exc.value.status_code == 429
