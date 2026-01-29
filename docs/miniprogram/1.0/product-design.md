# 微信小程序 MVP 产品设计：电影聊天 + 推荐 + 详情

目标：从 0 开发一个微信小程序，最小化落地“聊天 + 电影推荐 + 点击查看详情”的闭环：
- 用户在聊天里提出推荐/筛选问题（例如“推荐几部近期热门电影”）
- 系统返回：聊天文本（自然语言）+ 推荐电影的 `tmdb_id` 列表（机器可读）
- 小程序根据 `tmdb_id` 渲染电影卡片，点击进入电影详情页

范围：本 MVP 只覆盖 Movie（电影）；TV/Person 可按同样模式扩展。

相关文档：
- 前端实现：`docs/miniprogram/1.0/frontend-implementation.md`
- 后端实现：`docs/miniprogram/1.0/backend-implementation.md`
- UI 设计：`docs/miniprogram/1.0/ui-design.md`
- TMDB 端点参考：`docs/1.1.5/1.1.5.2/tmdb-api-reference.md`

---

## 1. 用户与使用场景

目标用户（MVP 画像）：
- 想快速找“最近能看”的电影：不想自己筛选榜单，偏好“省心推荐 + 一键看详情”
- 有明确条件（年份/语言/地区/类型）：希望在对话中表达意图，让系统给可执行的候选
- 喜欢追问：点开某部电影后继续问“导演/主演/同类型/类似作品”

典型场景（MVP 支持）：

1) 近期热门推荐
- 用户：“推荐几部近期热门的电影”
- 系统：给出 3-5 部 + 简短理由 + 可点击电影卡片。

2) 条件筛选推荐（年份/地区/语言/类型）
- 用户：“推荐 2024 年的高分电影，最好是中文片”
- 系统：给出候选；如果条件过宽/矛盾，进行 1 轮追问（例如“更偏爱情/动作？”）。

3) 追问某部电影
- 用户：点击卡片 → 看详情；或继续问：“这个导演还拍过什么？”
- 系统：基于 TMDB 入库数据（必要时叠加 GraphRAG/Enrichment）回答。

---

## 2. MVP 验收标准

- 聊天：流式输出可用（能逐步显示生成内容）
- 推荐：能稳定返回 `tmdb_id` 列表（机器可读，不依赖解析自然语言）
- 列表：小程序能根据 `tmdb_id` 拉到结构化字段并展示电影卡片
- 详情：点击卡片能进入详情页（至少：海报、标题、年份、简介、导演、主演、评分）

体验/性能基线（建议）：
- 首帧体验：用户发送后 1s 内有“生成中”反馈（哪怕只是 placeholder）
- 流式可感知：持续滚动更新（不需要逐字，但要持续增长）
- 详情页可用：点击卡片后 2s 内完成首屏渲染（海报可延迟）

---

## 3. 信息架构（MVP）

界面参考：`/Users/songxijun/workspace/miniprogram/miniprogram`（已有 TabBar + 自定义导航的整体风格）。

MVP 取舍原则：
- 只实现“聊天闭环 + 详情页跳转”，不做广场/消息/复杂个人中心。
- 保留底部 TabBar（降低学习成本），但 Tab 数量最小。

页面（建议）：
- TabBar（2 个 Tab）：
  - `Chat` → `pages/chat/chat`
  - `我的` → `pages/me/me`（极简：环境/baseURL、清空会话、版本号）
- 详情页（非 Tab）：
  - `pages/movie-detail/movie-detail?tmdb_id=603`

页面职责（MVP）：
- Chat：
  - 消息列表（user/assistant）
  - assistant 消息可附带“推荐卡片区”
  - 支持“新建会话”（重置 session）
- Movie Detail：
  - 展示电影基础信息
  - 允许“继续问这个电影”（可选：自动带引用/电影名）
- Me：
  - 环境切换（开发/测试/生产 baseURL）
  - 清空会话（仅清理本地 session_id 与本地消息缓存；不做服务端删除）

---

## 4. 核心交互流程（MVP）

### 4.1 聊天（含推荐卡片）

1) 用户发送一句话（文本）
2) UI 立即插入 user 消息，并插入一个 assistant placeholder（状态：生成中）
3) 后端流式返回：
  - `chunk`：逐步更新 assistant 文本
  - `recommendations`：返回 `tmdb_ids[]`
4) 收到 `recommendations` 后：
  - UI 立刻渲染“推荐卡片区 skeleton”
  - 调用后端批量接口拉 MovieCard 数据
  - 用 MovieCard 替换 skeleton
5) 收到 `complete`：
  - assistant 状态置为完成

### 4.2 点击电影卡片 → 详情页

1) 用户点击某个卡片
2) 进入详情页：先展示 skeleton
3) 请求 `GET /api/v1/mp/movies/{tmdb_id}`
4) 渲染详情字段；图片可后加载

---

## 5. MVP 功能清单（含不做项）

必须做（P0）：
- 流式聊天（chunk + complete）
- recommendations 输出（tmdb_ids 机器可读）
- movies/bulk：根据 tmdb_ids 渲染卡片
- movies/{id}：详情页
- 基础 UI：TabBar + Chat + Detail + Me（极简）

暂不做（明确不在 MVP）：
- 账号体系/微信登录（先匿名 user_id）
- 个人收藏/想看/已看（watchlist 相关）
- 多会话列表/历史会话管理（MVP 可以只有“当前会话”）
- 搜索页/榜单页（如需可用“空状态 feed”替代）
- 复杂过滤器 UI（先让用户用自然语言表达）

---

## 6. 文案与空状态（MVP）

Chat 空状态（建议）：
- 提示语：“想看什么类型？例如：近期热门、2024 中文高分、类似《喜宴》的电影”
- 快捷问题（3 个按钮，可选）：
  - “推荐近期热门”
  - “推荐 2024 高分”
  - “推荐华语爱情片”

错误/异常（MVP）：
- 网络失败：展示 toast + 保留已生成的部分文本
- 后端错误：assistant 消息显示“生成失败，请重试”，并允许一键重试（可选）

---

## 7. 数据口径与埋点（可选）

如果要做最小可用数据观察（可选）：
- chat_send（用户发送）
- chat_stream_complete（生成结束）
- recommendation_shown（推荐卡片区渲染完成）
- movie_card_click（点击卡片）
- movie_detail_loaded（详情加载成功/失败）

---

## 8. 分阶段计划

Phase 0（最小闭环）：
- Chat：流式聊天可用（逐字/逐片段显示）
- 推荐卡片：在聊天消息下挂载推荐卡片区
- 详情页：点击卡片跳详情页并展示基础信息

Phase 1（推荐体验增强）：
- 增加热门/近期 feed（空状态可展示）
- 推荐理由展示（卡片副标题/二级文本）

Phase 2（覆盖与质量）：
- 支持更强的过滤条件（year/region/lang/genre）
- 详情增强（images/videos/providers 等）
