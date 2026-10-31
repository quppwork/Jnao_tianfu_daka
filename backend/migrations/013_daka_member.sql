-- 本平台注册家长会员表（与 wx_member_snapshot 老库镜像分离）
-- wx_member_snapshot：只读镜像，定时从 db_fz_jingnao 同步，用于对比
-- daka_member：在本平台注册/登录产生的会员记录

CREATE TABLE IF NOT EXISTS daka_member (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_id INT NOT NULL COMMENT 'child_user.id, role=parent',
    mobile VARCHAR(20) NOT NULL,
    openid VARCHAR(64) NULL,
    unionid VARCHAR(64) NULL,
    register_channel VARCHAR(20) NOT NULL COMMENT 'sms|password|wechat|wechat_legacy',
    legacy_matched TINYINT NOT NULL DEFAULT 0 COMMENT '注册时是否命中 wx_member_snapshot',
    legacy_wx_member_id INT NULL,
    real_name VARCHAR(64) NULL,
    nickname VARCHAR(50) NULL,
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_daka_member_parent (parent_id),
    UNIQUE KEY uk_daka_member_mobile (mobile),
    UNIQUE KEY uk_daka_member_openid (openid),
    KEY idx_daka_member_legacy_wx (legacy_wx_member_id),
    FOREIGN KEY (parent_id) REFERENCES child_user(id)
);
