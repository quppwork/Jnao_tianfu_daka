-- 账户软删除：active | deleted
ALTER TABLE child_user
    ADD COLUMN account_status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'active=正常使用 deleted=已归档';
ALTER TABLE child_user
    ADD COLUMN deleted_at DATETIME NULL COMMENT '归档时间';
