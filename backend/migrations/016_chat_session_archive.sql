-- QA / Guide 会话归档表（定时任务将超期会话快照写入后从主表删除）
USE jnao_daka;

CREATE TABLE IF NOT EXISTS qa_session_archive (
    id INT PRIMARY KEY AUTO_INCREMENT,
    original_session_id INT NOT NULL COMMENT '原 qa_session.id',
    child_user_id INT NOT NULL,
    snapshot_json JSON NOT NULL COMMENT '会话 + messages 完整快照',
    archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_qa_archive_child (child_user_id, archived_at),
    INDEX idx_qa_archive_orig (original_session_id)
);

CREATE TABLE IF NOT EXISTS guide_session_archive (
    id INT PRIMARY KEY AUTO_INCREMENT,
    original_session_id INT NOT NULL COMMENT '原 guide_session.id',
    child_user_id INT NOT NULL,
    snapshot_json JSON NOT NULL COMMENT '会话 + messages 完整快照',
    archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_guide_archive_child (child_user_id, archived_at),
    INDEX idx_guide_archive_orig (original_session_id)
);
