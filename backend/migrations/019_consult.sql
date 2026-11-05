-- 在线咨询 Phase A：频道 / 会话 / 消息 SoT / Agent Job / 留言板
-- 由 create_all + seed 也可建表；本文件供人工/宝塔对照执行
USE jnao_daka;

CREATE TABLE IF NOT EXISTS consult_channel (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL COMMENT 'dayu/sizhe/...',
    kind VARCHAR(16) NOT NULL COMMENT 'group|dm',
    title VARCHAR(100) NOT NULL,
    bot_persona VARCHAR(64) NULL COMMENT 'Agent 人设 key',
    im_group_template VARCHAR(128) NULL COMMENT 'IM 群模板，待填',
    advisor_user_id INT NULL COMMENT '真人顾问 child_user.id，待填',
    ai_enabled TINYINT NOT NULL DEFAULT 1,
    human_handoff TINYINT NOT NULL DEFAULT 0,
    sort_order INT NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active|hidden|disabled',
    meta_json JSON NULL COMMENT 'chips/welcome/kb_route 等',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_consult_channel_code (code),
    KEY idx_consult_channel_status_sort (status, sort_order)
) COMMENT='咨询频道目录';

CREATE TABLE IF NOT EXISTS consult_conversation (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    channel_id BIGINT NOT NULL,
    parent_user_id INT NOT NULL,
    child_user_id INT NULL,
    kind VARCHAR(16) NOT NULL,
    im_conversation_id VARCHAR(128) NULL COMMENT 'IM 会话 ID，待填',
    status VARCHAR(24) NOT NULL DEFAULT 'open' COMMENT 'open|waiting_human|human|closed|board',
    assignee_id INT NULL,
    last_msg_at DATETIME NULL,
    last_msg_preview VARCHAR(200) NULL,
    unread_parent INT NOT NULL DEFAULT 0,
    unread_advisor INT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_consult_conv_im (im_conversation_id),
    KEY idx_consult_conv_parent (parent_user_id, updated_at),
    KEY idx_consult_conv_assignee (assignee_id, status),
    KEY idx_consult_conv_channel_parent (channel_id, parent_user_id),
    CONSTRAINT fk_consult_conv_channel FOREIGN KEY (channel_id) REFERENCES consult_channel(id)
) COMMENT='咨询会话';

CREATE TABLE IF NOT EXISTS consult_member (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    user_id INT NOT NULL DEFAULT 0 COMMENT 'bot 可用 0',
    role VARCHAR(16) NOT NULL COMMENT 'parent|advisor|bot|system',
    im_user_id VARCHAR(128) NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    left_at DATETIME NULL,
    UNIQUE KEY uk_consult_member (conversation_id, user_id, role),
    KEY idx_consult_member_user (user_id),
    CONSTRAINT fk_consult_member_conv FOREIGN KEY (conversation_id) REFERENCES consult_conversation(id)
) COMMENT='会话成员';

CREATE TABLE IF NOT EXISTS consult_message (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    client_msg_id VARCHAR(64) NULL,
    im_msg_id VARCHAR(128) NULL,
    sender_role VARCHAR(16) NOT NULL,
    sender_user_id INT NULL,
    content_type VARCHAR(16) NOT NULL DEFAULT 'text',
    content TEXT NOT NULL,
    meta_json JSON NULL,
    reply_to_id BIGINT NULL,
    visibility VARCHAR(16) NOT NULL DEFAULT 'all',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_consult_msg_im (im_msg_id),
    UNIQUE KEY uk_consult_msg_client (conversation_id, client_msg_id),
    KEY idx_consult_msg_conv_id (conversation_id, id),
    KEY idx_consult_msg_conv_time (conversation_id, created_at),
    CONSTRAINT fk_consult_msg_conv FOREIGN KEY (conversation_id) REFERENCES consult_conversation(id)
) COMMENT='咨询消息真相源';

CREATE TABLE IF NOT EXISTS consult_agent_job (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    trigger_msg_id BIGINT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    intent VARCHAR(32) NULL,
    model VARCHAR(64) NULL,
    kb_hits_json JSON NULL,
    tool_trace_json JSON NULL,
    result_msg_id BIGINT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    error TEXT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_consult_job_idem (idempotency_key),
    KEY idx_consult_job_status (status, id),
    KEY idx_consult_job_conv (conversation_id),
    CONSTRAINT fk_consult_job_conv FOREIGN KEY (conversation_id) REFERENCES consult_conversation(id)
) COMMENT='Agent 异步任务';

CREATE TABLE IF NOT EXISTS consult_advisor_presence (
    advisor_user_id INT PRIMARY KEY,
    app_online TINYINT NOT NULL DEFAULT 0,
    im_online TINYINT NOT NULL DEFAULT 0,
    available TINYINT NOT NULL DEFAULT 0,
    max_concurrent INT NOT NULL DEFAULT 5,
    active_count INT NOT NULL DEFAULT 0,
    last_seen_at DATETIME NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='顾问在线冷数据';

CREATE TABLE IF NOT EXISTS consult_board_post (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    channel_id BIGINT NOT NULL,
    parent_user_id INT NOT NULL,
    conversation_id BIGINT NULL,
    body TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'open',
    claimed_by INT NULL,
    reply_body TEXT NULL,
    reply_msg_id BIGINT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_consult_board_channel (channel_id, status),
    KEY idx_consult_board_parent (parent_user_id, created_at),
    CONSTRAINT fk_consult_board_channel FOREIGN KEY (channel_id) REFERENCES consult_channel(id)
) COMMENT='顾问留言板';
