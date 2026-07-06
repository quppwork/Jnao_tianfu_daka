-- 今日方案是否已手动编辑过（每训练日仅允许一次）
ALTER TABLE training_plan
    ADD COLUMN plan_customized TINYINT NOT NULL DEFAULT 0 COMMENT '1=用户已编辑过方案';
