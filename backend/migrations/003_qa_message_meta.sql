-- 学科答疑：消息图片与教练元数据
USE jnao_daka;

ALTER TABLE qa_message
    ADD COLUMN image_url VARCHAR(500) NULL AFTER voice_url,
    ADD COLUMN meta_json JSON NULL AFTER image_url;
