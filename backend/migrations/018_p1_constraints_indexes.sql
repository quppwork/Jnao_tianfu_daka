-- P1：唯一键与查询索引（与 models.py / migrate._apply_p1_constraints_and_indexes 对齐）
-- 线上若已手工执行可跳过；应用启动时 migrate 会幂等补齐。
-- 执行前请先查重复，避免 ADD UNIQUE 失败。

ALTER TABLE training_plan
  ADD UNIQUE KEY uk_training_plan_user_date (child_user_id, plan_date);

ALTER TABLE training_window
  ADD UNIQUE KEY uk_training_window_user_date (child_user_id, train_date),
  ADD INDEX idx_training_window_user (child_user_id);

ALTER TABLE parent_wechat_bind
  ADD UNIQUE KEY uk_wechat_openid_app (openid, app_id),
  ADD UNIQUE KEY uk_wechat_parent_app (parent_id, app_id);

ALTER TABLE parent_child_bind
  ADD UNIQUE KEY uk_parent_child (parent_id, child_id);
-- uk_parent_child_child_id 由既有补丁维护

ALTER TABLE content_item
  ADD INDEX idx_content_talent_sort (talent_code, lesson_sort);

ALTER TABLE training_record
  ADD INDEX idx_record_user_date (child_user_id, train_date),
  ADD INDEX idx_record_plan (plan_id),
  ADD INDEX idx_record_item (item_id);

ALTER TABLE guide_session
  ADD INDEX idx_guide_session_user (child_user_id);

ALTER TABLE qa_session
  ADD INDEX idx_qa_session_user (child_user_id);

ALTER TABLE talent_assessment
  ADD INDEX idx_talent_assessment_user (child_user_id);

ALTER TABLE wx_member_snapshot
  ADD INDEX idx_wx_snapshot_mobile (mobile),
  ADD INDEX idx_wx_snapshot_unionid (unionid);

ALTER TABLE user_session
  ADD INDEX idx_user_session_last_active (last_active_at);

ALTER TABLE qa_session_archive
  ADD INDEX idx_qa_archive_user_time (child_user_id, archived_at),
  ADD INDEX idx_qa_archive_orig (original_session_id);

ALTER TABLE guide_session_archive
  ADD INDEX idx_guide_archive_user_time (child_user_id, archived_at),
  ADD INDEX idx_guide_archive_orig (original_session_id);
