-- 微信家长登录：会员镜像 + openid 绑定（库：jnao_daka）

CREATE TABLE IF NOT EXISTS wx_member_snapshot (
    id INT PRIMARY KEY AUTO_INCREMENT,
    wx_member_id INT NULL,
    openid VARCHAR(64) NOT NULL,
    unionid VARCHAR(64) NULL,
    mobile VARCHAR(20) NULL,
    nickname VARCHAR(255) NULL,
    truename VARCHAR(64) NULL,
    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_wx_snapshot_openid (openid),
    KEY idx_wx_snapshot_mobile (mobile),
    KEY idx_wx_snapshot_unionid (unionid)
);

CREATE TABLE IF NOT EXISTS parent_wechat_bind (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_id INT NOT NULL,
    openid VARCHAR(64) NOT NULL,
    unionid VARCHAR(64) NULL,
    wx_member_id INT NULL,
    app_id VARCHAR(32) NOT NULL,
    bound_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_at DATETIME NULL,
    UNIQUE KEY uk_wechat_openid_app (openid, app_id),
    UNIQUE KEY uk_wechat_parent_app (parent_id, app_id),
    KEY idx_wechat_unionid (unionid),
    FOREIGN KEY (parent_id) REFERENCES child_user(id)
);
