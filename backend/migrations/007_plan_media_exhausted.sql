-- 用户设定时长用尽后不再提供音视频，但仍可打卡至训练日截止
ALTER TABLE training_plan
    ADD COLUMN media_exhausted TINYINT NOT NULL DEFAULT 0 COMMENT '1=不再推送媒体';
