-- 打卡记录保留训练日，删除 plan 后历史仍可查
ALTER TABLE training_record
    ADD COLUMN train_date DATE NULL AFTER item_id;

UPDATE training_record r
    INNER JOIN training_plan p ON r.plan_id = p.id
SET r.train_date = p.plan_date
WHERE r.train_date IS NULL AND p.plan_date IS NOT NULL;
