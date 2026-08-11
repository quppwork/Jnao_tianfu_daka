-- 成就/荣誉系统表
USE jnao_daka;

-- 勋章定义表
CREATE TABLE IF NOT EXISTS achievement_definition (
    id INT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL COMMENT '勋章唯一编码',
    name VARCHAR(100) NOT NULL COMMENT '勋章名称',
    title VARCHAR(50) NOT NULL COMMENT '称号（佩戴后显示）',
    description TEXT COMMENT '获取条件描述',
    category VARCHAR(20) NOT NULL COMMENT '分类：streak/skill/talent/milestone',
    condition_json JSON NOT NULL COMMENT '解锁条件JSON',
    icon_url VARCHAR(500) COMMENT '图标URL',
    color_theme VARCHAR(20) COMMENT '颜色主题：yellow/blue/purple/green/pink',
    sort_order INT DEFAULT 0,
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_achdef_code (code),
    INDEX idx_achdef_category (category, is_active)
);

-- 用户勋章状态表
CREATE TABLE IF NOT EXISTS user_achievement (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    achievement_id INT NOT NULL,
    status VARCHAR(20) DEFAULT 'locked' COMMENT 'locked/ready/claimed',
    progress_current INT DEFAULT 0,
    progress_target INT DEFAULT 1,
    unlocked_at DATETIME NULL,
    claimed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_achievement (user_id, achievement_id),
    INDEX idx_user_ach_user (user_id, status),
    INDEX idx_user_ach_achievement (achievement_id),
    FOREIGN KEY (achievement_id) REFERENCES achievement_definition(id)
);

-- 用户称号表
CREATE TABLE IF NOT EXISTS user_title (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL UNIQUE COMMENT '每个用户只能佩戴一个称号',
    title_code VARCHAR(50) NOT NULL COMMENT '称号编码（对应勋章定义）',
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_title_user (user_id, is_active)
);

-- 荣誉展柜表（3个槽位）
CREATE TABLE IF NOT EXISTS achievement_showcase (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    slot_index INT NOT NULL COMMENT '槽位索引：0,1,2',
    achievement_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_slot (user_id, slot_index),
    INDEX idx_showcase_user (user_id),
    FOREIGN KEY (achievement_id) REFERENCES achievement_definition(id)
);
