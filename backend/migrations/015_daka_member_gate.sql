-- 家长进门验证状态：进门一次写入，进门后 API 只读此字段，不重复 OAuth/查老库
ALTER TABLE daka_member
    ADD COLUMN wechat_bound_at DATETIME NULL COMMENT '微信 openid 绑定完成时间' AFTER updated_at,
    ADD COLUMN company_verified_at DATETIME NULL COMMENT '公司服务号手机验证完成时间' AFTER wechat_bound_at;

-- 已有 openid 绑定的账号回填
UPDATE daka_member
SET wechat_bound_at = COALESCE(wechat_bound_at, updated_at),
    company_verified_at = COALESCE(company_verified_at, updated_at)
WHERE openid IS NOT NULL AND openid != '';
