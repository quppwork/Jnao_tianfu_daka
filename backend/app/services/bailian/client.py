"""百炼 OpenAPI Client 工厂（AccessKey）。"""

from __future__ import annotations

from app.services.bailian.config import BailianConfig, load_bailian_config


def create_openapi_client(cfg: BailianConfig | None = None):
    from alibabacloud_bailian20231229.client import Client as BailianClient
    from alibabacloud_tea_openapi import models as open_api_models

    c = cfg or load_bailian_config()
    config = open_api_models.Config(
        access_key_id=c.access_key_id,
        access_key_secret=c.access_key_secret,
    )
    config.endpoint = c.endpoint
    return BailianClient(config)
