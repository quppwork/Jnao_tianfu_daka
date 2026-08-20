# 企业微信客户联系 API：员工外部好友（客户）数量

> 目标：看到「某员工添加了多少外部好友（客户）」。  
> 官方能力来自**服务端「客户联系」API**，不是小程序/客户端的 `wx.qy.openUserProfile`。

---

## 1. 先澄清：你给的链接能做什么

| 类型 | 接口 | 能否拿「加了多少好友」 |
| --- | --- | --- |
| 客户端（小程序） | [`wx.qy.openUserProfile`](https://developer.work.weixin.qq.com/document/path/93567) | **不能**。只是打开企业成员/外部联系人的个人信息页 |
| 服务端 | 客户联系 → 客户管理 / 统计管理 | **可以**。见下文 |

`openUserProfile` 参数：`type`（1=企业成员，2=外部联系人）、`userid`。前提是已 `wx.qy.login` 且 session 有效、当前成员在应用可见范围。它和「统计加好友数」无关。

---

## 2. 需求对照：你要哪种「多少」

| 业务问题 | 推荐接口 | 关键字段/算法 |
| --- | --- | --- |
| **管理后台「已服务的外部联系人」整表**（含添加人、进群时间） | [获取已服务的外部联系人](https://developer.work.weixin.qq.com/document/path/99434) | 分页拉 `contact_list`，按 `follow_userid` 分组计数 |
| **当前还剩多少外部客户**（按员工存量） | [获取客户列表](https://developer.work.weixin.qq.com/document/path/92113) | `len(external_userid)` |
| **某段时间新加了多少**（新增） | [获取「联系客户统计」数据](https://developer.work.weixin.qq.com/document/path/92275) | 按天汇总 `new_contact_cnt` |
| **同时要客户详情 / 添加时间 / 添加方式** | [批量获取客户详情](https://developer.work.weixin.qq.com/document/path/92994) | 分页拉全量后计数；`follow_info.createtime` / `add_way` |
| **先知道哪些员工开了客户联系** | [获取配置了客户联系功能的成员列表](https://developer.work.weixin.qq.com/document/path/92576) | `follow_user[]` |

**和你在后台看到的页面的对应关系：**

- 菜单：`客户联系与上下游 → 高级功能 → 已服务的外部联系人`
- 页面上的「共 18232」「客户 / 其他外部联系人」「添加人」列
- API：`POST /cgi-bin/externalcontact/contact_list`（见 §5.0）

**最常见落地：**

1. 要「和后台高级功能同一份已服务外部联系人」→ 调 `externalcontact/contact_list`，按 `follow_userid` 聚合。  
2. 要「员工 A 现在有多少外部客户」→ 调 `externalcontact/list`，数 ID 个数。  
3. 要「员工 A 近 7 天新加了多少」→ 调 `get_user_behavior_data`，把每天的 `new_contact_cnt` 相加。

---

## 3. 前置条件（不满足会查不到或报错）

1. 企业已开通并配置**客户联系**功能。  
2. 员工必须在「配置了客户联系功能的成员」里；否则其微信好友**不会**作为客户返回。  
3. 自建应用须加入「客户联系 → **可调用接口的应用**」，并用该应用 `secret` 取 `access_token`。  
   - 自 2023-12-01 起，一般不再支持用系统应用 secret 调这些接口。  
4. 被查询的 `userid` / 部门须在应用**可见范围**内。  
5. 统计接口额外需要「获取成员联系客户的数据统计」类权限（第三方应用权限名：企业客户权限 → 客户联系 → 获取成员联系客户的数据统计）。

---

## 4. 推荐调用链路

```text
access_token
    │
    ├─① get_follow_user_list     → 可统计的员工 userid 列表
    │
    ├─② externalcontact/list     → 单员工「当前客户数」= external_userid 长度
    │       或 batch/get_by_user → 批量拉详情后再按员工计数
    │
    └─③ get_user_behavior_data   → 按日「新增客户数」new_contact_cnt
```

---

## 5. 接口明细

### 5.0 获取已服务的外部联系人（对应管理后台「高级功能」页）

- 文档：https://developer.work.weixin.qq.com/document/path/99434  
- 管理后台：`客户联系与上下游 → 高级功能 → 已服务的外部联系人`  
- 方法：`POST`  
- URL：`https://qyapi.weixin.qq.com/cgi-bin/externalcontact/contact_list?access_token=ACCESS_TOKEN`

**请求示例：**

```json
{
  "cursor": "",
  "limit": 1000
}
```

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| cursor | 否 | 分页游标；首次不传。有效期约 4 小时，勿长期缓存 |
| limit | 否 | 每页条数，默认 1000 |

**权限：**

| 应用类型 | 要求 |
| --- | --- |
| 自建应用 | 配置到「客户联系 可调用接口的应用」 |
| 代开发 / 第三方 | **暂不支持** |

**字段与后台列对应：**

| 后台列 | API 字段 |
| --- | --- |
| 外部联系人名称 | 客户：`external_userid`；其他外部联系人：脱敏 `name` |
| 首次添加/进群时间 | `add_time` |
| 添加人 | `follow_userid` |
| 加入的外部群 | `chat_id` / `chat_name` |
| 客户 vs 其他外部联系人 | `is_customer` |
| 全量去重 | 一轮分页内用 `tmp_openid` 去重（仅当轮有效） |

**按员工统计「加了多少」：**

```text
按 follow_userid 分组
人数 = 该员工对应记录里去重后的 tmp_openid（或客户的 external_userid）个数
```

你们后台约 1.8 万条时，用 `limit=1000` 翻页约 19 次即可拉完。

---

### 5.1 获取配置了客户联系功能的成员列表

- 文档：https://developer.work.weixin.qq.com/document/path/92576  
- 方法：`GET`  
- URL：`https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get_follow_user_list?access_token=ACCESS_TOKEN`

**响应要点：**

```json
{
  "errcode": 0,
  "errmsg": "ok",
  "follow_user": ["zhangsan", "lisi"]
}
```

只有这些成员才有「客户」数据可查。

---

### 5.2 获取客户列表（存量好友数 —— 首选）

- 文档：https://developer.work.weixin.qq.com/document/path/92113  
- 方法：`GET`  
- URL：`https://qyapi.weixin.qq.com/cgi-bin/externalcontact/list?access_token=ACCESS_TOKEN&userid=USERID`

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| access_token | 是 | 调用凭证 |
| userid | 是 | 企业成员 userid |

**响应示例：**

```json
{
  "errcode": 0,
  "errmsg": "ok",
  "external_userid": [
    "woAJ2GCAAAXtWyujaWJHDDGi0mACAAA",
    "wmqfasd1e1927831291723123109rAAA"
  ]
}
```

**计算方式：**

```text
员工当前外部客户数 = external_userid 数组长度
```

说明：

- 「客户」= 配置了客户联系功能的成员所添加的外部联系人。  
- 未配置客户联系的成员，其外部好友不会出现在此列表。  
- 应用只能拿到可见范围内成员的数据。

---

### 5.3 获取「联系客户统计」数据（时间段新增 —— 首选）

- 文档：https://developer.work.weixin.qq.com/document/path/92275（企业内部开发同源：[92132](https://developer.work.weixin.qq.com/document/path/92132)）  
- 方法：`POST`  
- URL：`https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get_user_behavior_data?access_token=ACCESS_TOKEN`

**请求示例：**

```json
{
  "userid": ["zhangsan"],
  "start_time": 1536508800,
  "end_time": 1536595200
}
```

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| userid | 否* | 成员 ID 列表，最多 100 个 |
| partyid | 否* | 部门 ID 列表，最多 100 个 |
| start_time | 是 | 起始时间戳（会向下取整到当日 0 点） |
| end_time | 是 | 结束时间戳 |

\* `userid` 与 `partyid` 不可同时为空。

**限制：**

- 按**天**返回；区间为闭区间 `[start_time, end_time]`。  
- 单次查询跨度最大 **30 天**。  
- 最多查最近 **180 天**。  
- 传入多个 `userid` 时，返回的是这些成员的**合计**数据（不是按人拆开）。若要「每人一条」，需**每人单独请求**，或只传一个 userid。

**响应中与「加好友」直接相关的字段：**

| 字段 | 含义 |
| --- | --- |
| `new_contact_cnt` | **新增客户数**：成员新添加的客户数量 |
| `new_apply_cnt` | 发起申请数（主动发好友申请，不等于已加上） |
| `negative_feedback_cnt` | 删除/拉黑该成员的客户数 |
| `chat_cnt` / `message_cnt` | 聊天数 / 发消息数（运营指标，非好友数） |

**计算某员工近 N 天新增客户数：**

```text
sum(behavior_data[].new_contact_cnt)
```

注意区分：

- `new_apply_cnt`：发出去多少申请  
- `new_contact_cnt`：真正新加上多少客户（更接近「新加了多少外部好友」）

---

### 5.4 批量获取客户详情（存量 + 明细）

- 文档：https://developer.work.weixin.qq.com/document/path/92994  
- 方法：`POST`  
- URL：`https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token=ACCESS_TOKEN`

**请求示例：**

```json
{
  "userid_list": ["zhangsan", "lisi"],
  "cursor": "",
  "limit": 100
}
```

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| userid_list | 是 | 成员 userid，最多 100 个 |
| cursor | 否 | 分页游标 |
| limit | 否 | 每页最多 100，默认 50 |

用 `next_cursor` 翻页直到为空，对某员工相关记录计数即可得到存量；`follow_info` 里可看添加时间、添加渠道等。人多时比反复调 `list` 更适合做同步任务。

---

### 5.5 获取客户详情（单客户）

- 文档：https://developer.work.weixin.qq.com/document/path/92265  
- 方法：`GET`  
- URL：`https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get?access_token=ACCESS_TOKEN&external_userid=EXTERNAL_USERID`  

用于查单个外部联系人详情及跟进人，不适合用来「数全员好友总量」（应优先用 `list` / `batch/get_by_user`）。

---

## 6. 落地伪代码（按员工出报表）

```python
# 伪代码：每个员工「当前客户数」+「近7天新增」

follow_users = get_follow_user_list()  # ①

report = []
for uid in follow_users:
    # ② 存量
    ids = externalcontact_list(userid=uid)
    current_cnt = len(ids["external_userid"])

    # ③ 近7天新增（每人单独请求，避免多人合计）
    behavior = get_user_behavior_data(
        userid=[uid],
        start_time=day0_ts_7_days_ago,
        end_time=day0_ts_today,
    )
    new_7d = sum(d.get("new_contact_cnt", 0) for d in behavior["behavior_data"])

    report.append({
        "userid": uid,
        "current_external_friends": current_cnt,
        "new_contacts_7d": new_7d,
    })
```

---

## 7. 管理后台对照（不写代码时）

企业微信管理端也可人工查看联系客户相关统计（路径随版本略有差异），大致在：

**客户联系 / 客户与上下游 → 统计** 一类菜单。

API 侧与后台「联系客户统计」对应的就是 `get_user_behavior_data`；「某个成员名下客户列表」对应 `externalcontact/list`。

---

## 8. 常见坑

| 现象 | 原因 |
| --- | --- |
| 员工明明有微信好友，接口返回空 | 该员工未配置客户联系功能，或好友未成为「客户」 |
| 统计接口有数、list 很少 | 统计是时间段「新增」；list 是「当前仍在」的客户（删好友后会变少） |
| 多人传入 userid 后人数对不上 | `get_user_behavior_data` 多 userid 是**合计**，不是按人拆分 |
| 查不到 180 天前数据 | 官方限制：行为统计最多最近 180 天 |
| 一次查超过 30 天失败 | 需拆成多个 ≤30 天的请求再汇总 |
| `openUserProfile` 调不通 / 无数据 | 那是打开资料页的客户端 API，本身不返回数量 |

---

## 9. 官方文档索引

| 文档 | 链接 |
| --- | --- |
| 打开个人信息页（客户端，非统计） | https://developer.work.weixin.qq.com/document/path/93567 |
| 客户联系概述 | https://developer.work.weixin.qq.com/document/path/92109 |
| **获取已服务的外部联系人（高级功能页）** | https://developer.work.weixin.qq.com/document/path/99434 |
| 配置了客户联系的成员列表 | https://developer.work.weixin.qq.com/document/path/92576 |
| 获取客户列表 | https://developer.work.weixin.qq.com/document/path/92113 |
| 获取客户详情 | https://developer.work.weixin.qq.com/document/path/92265 |
| 批量获取客户详情 | https://developer.work.weixin.qq.com/document/path/92994 |
| 获取「联系客户统计」数据 | https://developer.work.weixin.qq.com/document/path/92275 |

---

## 10. 结论（直接选型）

- **要对齐管理后台「已服务的外部联系人」**：`POST /cgi-bin/externalcontact/contact_list` → 按 `follow_userid` 聚合（仅自建应用）。  
- **看员工现在加了多少外部客户**：`GET /cgi-bin/externalcontact/list` → 数 `external_userid`。  
- **看员工某段时间新加了多少**：`POST /cgi-bin/externalcontact/get_user_behavior_data` → 汇总 `new_contact_cnt`（按人单独查）。  
- **`wx.qy.openUserProfile`**：只能打开资料页，不能做好友数量统计。

---

## 11. 本仓库同步脚本（写入 db_fz_jingnao）

### 11.1 推荐结构（方案 A：2 张表，近原样）

脚本：`backend/tools/export_wework_served_plan_a.py`

| 表名 | 用途 |
| --- | --- |
| `qywx_served_record` | `contact_list` 明细原字段 + 姓名预留列 |
| `qywx_served_stat` | 按添加人去重汇总（二次统计，非接口原表） |

```powershell
python backend/tools/export_wework_served_plan_a.py --from-json docs/export/qywx_served_contacts_XXXX.json --since-days 7
```

`--since-days` **只影响导出哪些行**，不会往表里写「近7天」一类标签字段。

明细列与接口对应：`is_customer, tmp_openid, external_userid, follow_userid, chat_id, add_time, name, chat_name`；另加预留 `follow_name`。

```sql
SELECT * FROM qywx_served_record ORDER BY add_time DESC LIMIT 20;
SELECT * FROM qywx_served_stat ORDER BY contact_cnt DESC LIMIT 20;
```

补全脚本（可选）：`backend/tools/enrich_wework_served_contacts.py`  
旧分表脚本：`backend/tools/split_wework_served_tables.py`（已不推荐）

### 11.2 拉取缓存脚本

脚本：`backend/tools/sync_wework_served_contacts.py`

早期宽表（已弃用，分表 SQL 会 DROP）：

| 表名 | 用途 |
| --- | --- |
| `qywx_served_external_contact` | 旧明细宽表 |
| `qywx_served_external_contact_stat` | 旧汇总表 |

环境变量（写在本地 `backend/.env`，勿提交仓库）：

```text
WEWORK_CORPID=...
WEWORK_CORPSECRET=...
WEWORK_AGENTID=...
LEGACY_DATABASE_URL=mysql+pymysql://...@.../db_fz_jingnao
```

运行：

```powershell
$env:PYTHONIOENCODING="utf-8"
python backend/tools/sync_wework_served_contacts.py --dry-run   # 只拉不写
python backend/tools/sync_wework_served_contacts.py             # 全量覆盖写入
```

**IP 白名单（errcode 60020）：**  
企业微信不允许未授权 IP 调用。需在管理后台为该自建应用配置**企业可信 IP**，加入：

- 本机出口 IP（本地跑脚本时），或  
- 阿里云服务器公网 IP（在 `jnaosoft.cn` 上跑时）

路径一般在：应用详情 → 企业可信 IP / 开发者接口 IP 配置（以控制台实际文案为准）。
