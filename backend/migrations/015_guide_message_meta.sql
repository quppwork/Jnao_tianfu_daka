-- 首页引导：assistant 消息元数据（actions / tools_used）
-- SQLite 兼容（单列 ALTER）
-- USE jnao_daka;

ALTER TABLE guide_message ADD meta_json JSON;
