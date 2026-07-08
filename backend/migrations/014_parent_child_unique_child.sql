-- 一个孩子只能绑定一个家长（执行前 migrate.py 会去重）
-- MySQL 生产可手动执行；开发环境由 migrate.py 自动应用

ALTER TABLE parent_child_bind
  ADD UNIQUE KEY uk_parent_child_child_id (child_id);
