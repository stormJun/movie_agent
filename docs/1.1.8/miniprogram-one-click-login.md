# 小程序一键登录（WeChat MiniProgram Login）技术方案（MVP）

目标：为小程序端提供“微信一键登录”，让后端能拿到稳定的 `user_id`（基于 openid/unionid），替代当前前端用 `randomId('u')` 生成的 `mp_user_id`，并为后续“跨端数据一致/用户画像/记忆/反馈归因”打基础。

本方案面向 MVP：先做“静默登录（openid 级别）+ 业务 token（JWT）”，可选再扩展手机号一键登录。

---

## 1. 现状与问题

当前小程序实现（`miniprogram/pages/chat/index.ts`）：
- `mp_user_id`：本地随机生成并写入 `wx.setStorageSync('mp_user_id', ...)`
- `mp_session_id`：本地随机生成（用于对话会话）

问题：
- `mp_user_id` 不稳定（卸载/清缓存会变），无法作为后端用户主键。
- 无法进行权限/用户级数据隔离（收藏、watchlist、记忆、反馈、历史会话等）。
- 之前出现过 `tourist appid` / `41001` 等错误：说明需要以“真实小程序 AppID + AppSecret”的服务器端换取登录态，而不是依赖开发者工具的“游客模式”。

---

## 2. 术语与边界

- WeChat 登录态：`wx.login()` 获取 `code`，后端用 `code2Session` 换取 `openid/session_key/unionid`。
- 业务登录态：后端基于 `openid` 创建/查找用户后，签发自己的 `access_token`（建议 JWT）。
- 对话会话：`session_id`（conversation/session）仍然由前端生成或后端生成，用来区分“这一段聊天”，它不等价于登录态。

---

## 3. MVP 登录流程（静默登录）

### 3.1 前端流程（小程序）

触发点：`App.onLaunch` 或进入核心页面（如 Chat 页）时执行一次。

步骤：
1) 读取本地 token
   - `mp_access_token`（建议 storage key）
   - 若存在，则直接带 token 调后端；若 401/过期，再走登录流程

2) 调用 `wx.login()` 获取 `code`
   - `code` 有效期 5 分钟；必须尽快发给后端

3) 调后端登录接口：`POST /api/v1/mp/auth/login`
   - request: `{ code: string }`
   - response: `{ access_token: string, expires_in: number, user: { user_id: string } }`

4) 写入本地 storage
   - `mp_access_token = access_token`
   - `mp_user_id = user.user_id`（以后 chat 请求不再随机生成）

5) 每次请求自动带上 `Authorization: Bearer <access_token>`
   - 包括：HTTP JSON 请求（`miniprogram/utils/http.ts`）与流式请求（`miniprogram/utils/mpStreamClient.ts`）

失败兜底：
- 如果登录失败（网络/后端未配置），MVP 可降级为“匿名模式”（继续用 randomId），但**产品上建议明确提示**并禁止写用户级数据（如 watchlist/反馈）。

### 3.2 后端流程（服务端）

接口：`POST /api/v1/mp/auth/login`

步骤：
1) 校验参数 `code` 非空
2) 调用微信接口换取 session：
   - `GET https://api.weixin.qq.com/sns/jscode2session`
   - query: `appid, secret, js_code, grant_type=authorization_code`
3) 解析返回：
   - 成功：`openid`, `session_key`, 可能有 `unionid`
   - 失败：`errcode/errmsg`（例如 `40029` 无效 code，`40125` appsecret 错误，`41001` 缺少 appid 等）
4) Upsert 用户：
   - 用 `(provider='wechat_mp', openid)` 作为唯一键
   - 生成内部 `user_id`（UUID 或自增），写入 `last_login_at`
5) 生成业务 token（JWT）：
   - claims：`sub=user_id`、`provider=wechat_mp`、`openid`（可选）
   - 过期：例如 7 天（MVP 可不做 refresh_token，过期重新登录即可）
6) 返回给前端

---

## 4. API 设计（建议）

### 4.1 登录

`POST /api/v1/mp/auth/login`

request:
```json
{ "code": "wx.login返回的code" }
```

response:
```json
{
  "access_token": "Bearer token (JWT)",
  "expires_in": 604800,
  "user": {
    "user_id": "u_xxx",
    "provider": "wechat_mp"
  }
}
```

### 4.2 获取当前用户（可选）

`GET /api/v1/mp/auth/me`

response:
```json
{ "user_id": "u_xxx", "provider": "wechat_mp" }
```

用途：前端启动时验证 token 是否有效；也可用 401 来触发重新登录。

---

## 5. 数据库建模（MVP）

考虑到本项目偏“代码内 ensure_schema”模式（例如 `tmdb_store.py`/`feedback_store.py`），建议新增 schema：`mp`。

### 5.1 mp.users（小程序用户表）

字段建议：
- `id`：内部用户 id（UUID/text）
- `provider`：固定 `wechat_mp`
- `openid`：微信 openid（唯一）
- `unionid`：可空（需要用户在开放平台绑定/或特定条件下返回）
- `created_at` / `updated_at` / `last_login_at`

唯一约束：
- `UNIQUE(provider, openid)`

### 5.2 mp.sessions（业务 token 会话，可选）

MVP 如果用纯 JWT 且不做 server-side revoke，可以先不建表。

如果需要“注销/强制下线/黑名单/审计”，可加：
- `token_jti`（或 token_hash）
- `user_id`
- `created_at` / `expires_at`
- `revoked_at`

---

## 6. 配置与安全

### 6.1 必需环境变量（后端）

- `WECHAT_MP_APPID`
- `WECHAT_MP_APPSECRET`

说明：
- 绝不能下发到小程序端
- 本地开发建议写在 `.env`（不要提交）

### 6.2 安全要点

- 只信任服务端 `code2session` 返回的 `openid`；前端不得自报 openid。
- `code` 一次性且短期有效，后端应拒绝空/过期 code。
- JWT 签名密钥独立配置（例如 `MP_JWT_SECRET`），并设置合理过期时间。
- 所有 `mp` 接口（chat/feedback/watchlist 等）逐步改为：
  - `user_id` 从 token 解析得到
  - 前端不再传 `user_id`

---

## 7. 与现有业务的集成建议

### 7.1 Chat

现状：`/api/v1/mp/chat/stream` 请求体包含 `user_id/session_id`。

建议：
- `session_id`：仍由前端生成（“对话会话 id”，用于新会话/清空等）
- `user_id`：改为从 `Authorization` token 解析；请求体中移除，避免伪造

### 7.2 反馈 / watchlist / 记忆

同样遵循：
- 写入必须绑定 `user_id`
- 未登录时可只允许浏览（读接口），或提示用户先登录

---

## 8. “手机号一键登录”（可选扩展）

如果后续需要手机号：
- 前端：使用按钮触发 `wx.getPhoneNumber`（新版本可能返回 `code`）
- 后端：调用微信 `phonenumber.getPhoneNumber` 解密（需要 `access_token`）

注意：手机号能力通常需要额外的微信侧配置/类目/审核；不建议作为 MVP 必选项。

---

## 9. 开发者工具与常见报错

- `tourist appid`：开发者工具使用游客模式，无法进行真实登录态换取。解决：使用真实 AppID（`project.config.json` 配置）并在后端配好 AppSecret。
- `41001`：缺少 appid；通常是后端未配置 `WECHAT_MP_APPID` 或请求拼参错误。
- `40125`：appsecret 错误（最常见：secret 配错或用了别的小程序的 secret）。
- `40029`：code 无效/过期（code 用完、过了 5 分钟、或重复使用）。

