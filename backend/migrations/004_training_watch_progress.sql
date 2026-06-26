-- 训练项视频观看进度（JSON: watched_sec, duration_sec, pct）
ALTER TABLE training_item ADD COLUMN watch_progress JSON NULL;
