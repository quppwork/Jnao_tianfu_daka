-- 学科答疑：消息图片与教练元数据
-- SQLite 兼容（单列 ALTER，无 AFTER）
-- USE jnao_daka;

ALTER TABLE qa_message ADD image_url TEXT;
ALTER TABLE qa_message ADD meta_json TEXT;
