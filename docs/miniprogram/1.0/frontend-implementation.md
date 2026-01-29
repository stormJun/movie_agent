# 微信小程序前端实现说明（MVP）

实现约束（本项目约定）：
- 小程序工程目录：`miniprogram/`（本仓库）
  - 已“拍平”：`project.config.json` 与 `app.json` 同级（不再使用 `miniprogram/miniprogram/` 双层目录）
- 参考技术栈与代码结构：`/Users/songxijun/workspace/miniprogram/miniprogram`
  - 原生小程序 + TypeScript + Less + mobx-miniprogram
  - 重点复用其组织方式：`api/`（HTTP 封装）、`services/service-env/`（环境与 baseURL）、`stores/`、`utils/`
  - 流式请求参考：`utils/http-ai/StreamHttpClient.ts` + `api/api-http-stream.ts`

后端接口前缀（小程序专用）：`/api/v1/mp/*`（见 `docs/miniprogram/1.0/backend-implementation.md`）
UI 规格（可落地清单）：`docs/miniprogram/1.0/ui-design.md`

---

## 1. 页面与导航（MVP）

TabBar（建议 2 个 Tab）：
- `Chat` → `pages/chat/chat`
- `我的` → `pages/me/me`（极简设置）

非 Tab 页面：
- 电影详情：`pages/movie-detail/movie-detail?tmdb_id=603`

建议的目录骨架（对齐模板习惯）：
- `miniprogram/pages/chat/`
- `miniprogram/pages/movie-detail/`
- `miniprogram/pages/me/`
- `miniprogram/utils/`（API 与流式 SSE client）

---

## 2. Chat 页面（核心交互）

消息形态（MVP）：
- user 消息：纯文本气泡
- assistant 消息：流式拼接文本 +（可选）推荐卡片区

推荐卡片区（Message attachment）：
- 标题：例如“为你推荐（近期热门）”
- 卡片列表：poster + title + year + rating
- 点击卡片：`wx.navigateTo({ url: \`/pages/movie-detail/movie-detail?tmdb_id=${id}\` })`

UI 细节规格（直接对齐 UI 文档，避免二义性）：
- 消息气泡：优先复用模板 `pages/ai-agent/components/agent-message-block`（light theme）
- “生成中”：复用模板 `pages/ai-agent/components/agent-message-process`（三点 typing）
- 推荐卡片区：固定卡片宽 `240rpx`，海报 `240rpx x 320rpx`，圆角 `24rpx`，bulk 返回前渲染 3 个 skeleton
- 回到底部按钮：`56rpx` 圆形，出现条件与位置参照模板（`bottom = inputBarHeight + 24px`）

状态机（建议，避免边界 bug）：
- `idle`：可输入/可发送
- `connecting`：已发起请求，等待首个 frame
- `streaming`：持续收到 `chunk`
- `done`：收到 `complete`
- `error`：收到 `error` 或请求失败（允许重试/继续显示已生成文本）

---

## 3. 流式请求（HTTP chunk + SSE）

结论：小程序不支持浏览器 `EventSource`，但可以用：
- `wx.request({ enableChunked: true })`
- `requestTask.onChunkReceived(...)`
- SSE 解析器（`data: ...\n\n`）

参考工程已实现完整链路：
- `utils/http-ai/StreamHttpClient.ts`
  - `enableChunked: true`
  - `onChunkReceived` 收分块
  - UTF-8 边界处理（避免中文乱码）
  - `sse-parser.ts` 增量解析 SSE
- 业务使用方式：
  - `api/api-http-stream.ts` 提供 `streamPost(...)`
  - controller 里按 `type` 分发：
    - `type === 'chunk'` → 追加文本
    - `type === 'complete'` → 收尾

MVP 建议直接复用同样的封装与分发约定（后端会做映射层，保证 `type` 兼容）。

推荐的调用方式（对齐模板 controller 思路）：
- 发送时：
  - 保存 `currentTask = streamPost(...)`，并把输入框置灰
  - 插入一条 assistant placeholder（空文本 + typing）
- onData：
  - `chunk`：append 文本并 setData；调用 `scrollChatToBottom()`（可用 layout controller 模式）
  - `recommendations`：触发 movies/bulk 拉卡片，更新该 assistant 消息的附件区域
  - `complete`：收尾并清理 `currentTask`
- onError/onComplete：
  - 取消/清理 `currentTask`
  - 如果已有部分文本：保留；否则显示错误占位 + toast

页面生命周期注意：
- `onUnload`/`onHide`：如果仍在生成，调用 `currentTask.cancel()`（避免后台继续占用连接）

---

## 4. SSE 数据帧（小程序端消费）

最小帧类型（MVP 必需）：

1) 生成开始
```json
{ "type": "generate_start", "content": { "request_id": "..." } }
```

2) 增量文本
```json
{ "type": "chunk", "content": "……" }
```

3) 推荐列表（一次性）
```json
{
  "type": "recommendations",
  "content": { "tmdb_ids": [603, 27205], "title": "为你推荐（近期热门）", "mode": "movie_popular" }
}
```

4) 生成完成
```json
{ "type": "complete", "content": null, "answer": "（可选，最终全文）" }
```

前端处理建议：
- `generate_start`：初始化本轮 assistant 消息容器（清空累积文本、记录 request_id）
- `chunk`：append 到 `accumulatedContent` 并 setData 更新 UI
- `recommendations`：调用 `POST /api/v1/mp/movies/bulk` 拉 MovieCard 列表并渲染卡片
- `complete`：结束状态；如 `answer` 存在可作为最终文本兜底

movies/bulk 的调用策略（避免重复请求）：
- 对 `tmdb_ids` 去重、保持顺序
- 本地做一个 `Map<tmdb_id, MovieCard>` 缓存（page 级或 store 级）
- bulk 返回后只更新缺失的卡片；缺失 id 用“无数据卡片”（title=未知）兜底

接口返回示例（便于前端直接写 types）：
```ts
export type MovieCard = {
  tmdb_id: number;
  title: string;
  release_date: string | null;
  year: number | null;
  poster_url: string | null;
  vote_average: number | null;
  vote_count: number | null;
  directors: string[];
  top_cast: string[];
};

export type MoviesBulkResponse = {
  items: MovieCard[];
  missing_ids: number[];
};
```

---

## 5. 电影详情页（MVP）

入参：`tmdb_id`

请求：
- `GET /api/v1/mp/movies/{tmdb_id}`

展示字段（MVP）：
- 海报/背景图
- 标题（含原始标题）
- 上映年份、片长、类型
- 评分（vote_average/vote_count）
- 导演（从 crew 取 job=Director）
- 主演（cast 前 N）
- 简介

详情页布局建议：
- 结构：`zh-nav-bar` + `zh-layout` + scroll
- Hero：backdrop 顶图（无则渐变底）+ poster（`240rpx x 320rpx`）+ 标题/副标题/评分
- 内容：3 个 `zh-card`（剧情简介 / 基本信息 / 演职员）
- Loading：hero skeleton + 3 个 card skeleton；失败用 `zh-layout` 的 network-error

---

## 6. 网络与环境切换（MVP）

- `user_id`：首次启动生成 UUID 并 `wx.setStorageSync` 保存
- `session_id`：进入 chat 时生成并保存；“新建会话”时重置
- baseURL：复用参考模板的 `services/service-env/`（环境配置 / env-switch 页面）
- 小程序域名：需配置 `request合法域名`（本地联调可通过代理/内网穿透）

本地标识（建议）：
- `user_id`：首次启动生成 UUID；存储 key 示例：`mp_user_id`
- `session_id`：每次“新建会话”生成新的 UUID；存储 key 示例：`mp_session_id`

联调注意（小程序流式）：
- 开发者工具/代理/网关可能会缓冲 chunk，导致“看起来不流式”
- 直连后端时优先确保后端返回 `X-Accel-Buffering: no`（见后端文档）
- 微信开发者工具可在“详情/本地设置”里开启：
  - `不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书`
  用于本地联调（上线前必须按微信规范配置正式域名）

---

## 7. 图片 URL 拼接（MVP）

MVP 可先用 TMDB 公共图片域名（不依赖 `/configuration`）：
- poster：`https://image.tmdb.org/t/p/w500{poster_path}`
- backdrop：`https://image.tmdb.org/t/p/w780{backdrop_path}`

缺图兜底（建议）：
- poster_path/backdrop_path 为空：使用本地占位图（后续可加一张 `placeholder-poster.png`）
