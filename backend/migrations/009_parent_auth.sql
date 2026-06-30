-- 家长/孩子账号体系：密码登录 + 家长-孩子绑定
-- SQLite 开发环境由 migrate.py 幂等补丁 + create_all 同步

ALTER TABLE child_user ADD COLUMN password_hash VARCHAR(128) NULL;
ALTER TABLE child_user ADD COLUMN role VARCHAR(10) NOT NULL DEFAULT 'student';
ALTER TABLE child_user ADD COLUMN login_name VARCHAR(50) NULL;
ALTER TABLE child_user ADD COLUMN child_quota INT NULL COMMENT '家长可分配孩子名额上限，NULL=默认';

CREATE UNIQUE INDEX IF NOT EXISTS uk_child_user_login_name ON child_user(login_name);
CREATE INDEX IF NOT EXISTS idx_child_user_parent_phone_role ON child_user(parent_phone, role);

CREATE TABLE IF NOT EXISTS parent_child_bind (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_id INT NOT NULL,
    child_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_parent_child (parent_id, child_id),
    FOREIGN KEY (parent_id) REFERENCES child_user(id),
    FOREIGN KEY (child_id) REFERENCES child_user(id)
);
