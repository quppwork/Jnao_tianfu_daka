-- JNAO MVP 数据库建表脚本
-- 库名: jnao_daka（MySQL）
-- SQLite 开发环境由 SQLAlchemy create_all 自动建表

CREATE DATABASE IF NOT EXISTS jnao_daka DEFAULT CHARSET utf8mb4;
USE jnao_daka;

CREATE TABLE IF NOT EXISTS child_user (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_phone VARCHAR(20) NOT NULL COMMENT '家长手机号',
    nickname VARCHAR(50) NOT NULL COMMENT '孩子姓名',
    jnao_uid VARCHAR(50) COMMENT 'JNAO 测评 uid',
    profile_json JSON COMMENT '进 App 后完善',
    training_level VARCHAR(20) COMMENT '训练等级',
    is_qingbei TINYINT DEFAULT 0 COMMENT '是否清北班',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS talent_assessment (
    id INT PRIMARY KEY AUTO_INCREMENT,
    child_user_id INT NOT NULL,
    jnao_record_id VARCHAR(50),
    answer_bitstring VARCHAR(35),
    test_type TINYINT DEFAULT 1 COMMENT '1=儿童',
    talent_primary VARCHAR(20),
    talent_tag VARCHAR(5),
    talent_code TINYINT,
    report_json JSON,
    assessed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (child_user_id) REFERENCES child_user(id)
);

CREATE TABLE IF NOT EXISTS content_item (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_id INT COMMENT '老库 ys_c_av.id',
    course_id INT,
    talent_code TINYINT NOT NULL,
    talent_tag VARCHAR(5),
    lesson_title VARCHAR(200),
    lesson_sort INT NOT NULL DEFAULT 0,
    play_url VARCHAR(500) NOT NULL,
    video_url VARCHAR(500),
    content_type VARCHAR(10) DEFAULT 'audio',
    duration_min INT,
    instructions TEXT,
    status TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_talent_sort (talent_code, lesson_sort)
);

CREATE TABLE IF NOT EXISTS training_plan (
    id INT PRIMARY KEY AUTO_INCREMENT,
    child_user_id INT NOT NULL,
    plan_date DATE NOT NULL,
    level VARCHAR(20),
    report_text TEXT,
    planned_minutes INT,
    content_index INT NOT NULL DEFAULT 0 COMMENT '当前系列序号',
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/completed',
    generated_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_date (child_user_id, plan_date),
    FOREIGN KEY (child_user_id) REFERENCES child_user(id)
);

CREATE TABLE IF NOT EXISTS training_item (
    id INT PRIMARY KEY AUTO_INCREMENT,
    plan_id INT NOT NULL,
    sort_order INT NOT NULL,
    ability_type VARCHAR(20),
    title VARCHAR(200),
    duration_min INT,
    video_url VARCHAR(500),
    audio_url VARCHAR(500),
    instructions TEXT,
    content_item_id INT,
    checkin_status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/done',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES training_plan(id)
);

CREATE TABLE IF NOT EXISTS training_record (
    id INT PRIMARY KEY AUTO_INCREMENT,
    child_user_id INT NOT NULL,
    plan_id INT,
    item_id INT,
    ability_type VARCHAR(20),
    time_spent VARCHAR(50),
    content TEXT,
    result TEXT,
    note TEXT,
    attitude_pct INT,
    files_json JSON,
    review_status VARCHAR(20) DEFAULT 'approved',
    reviewed_by INT,
    reviewed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (child_user_id) REFERENCES child_user(id)
);

CREATE TABLE IF NOT EXISTS training_window (
    id INT PRIMARY KEY AUTO_INCREMENT,
    child_user_id INT NOT NULL,
    train_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_date (child_user_id, train_date)
);

CREATE TABLE IF NOT EXISTS qa_session (
    id INT PRIMARY KEY AUTO_INCREMENT,
    child_user_id INT NOT NULL,
    title VARCHAR(200),
    subject VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS qa_message (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id INT NOT NULL,
    role VARCHAR(10) NOT NULL,
    content TEXT NOT NULL,
    voice_url VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES qa_session(id)
);
