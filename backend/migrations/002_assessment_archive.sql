-- 测评删除归档表（删除前写入，配合定时全库备份）
USE jnao_daka;

CREATE TABLE IF NOT EXISTS talent_assessment_archive (
    id INT PRIMARY KEY AUTO_INCREMENT,
    original_id INT NOT NULL COMMENT '原 talent_assessment.id',
    child_user_id INT NOT NULL,
    snapshot_json JSON NOT NULL COMMENT '删除时完整快照',
    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_child_deleted (child_user_id, deleted_at)
);
