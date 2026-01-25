import React, { useEffect, useMemo, useState } from "react";
import { Drawer, Card, Typography, Space, Skeleton, Tag, Button, Popconfirm, Empty, message, Input, Segmented, Modal, InputNumber } from "antd";
import { CloseOutlined } from "@ant-design/icons";
import type { MemoryDashboardResponse, WatchlistItemDto, WatchlistStatus } from "../../types/memoryCenter";
import { addWatchlistItem, dedupMergeWatchlist, deleteMemoryItem, deleteWatchlistItem, getMemoryDashboard, listWatchlist, restoreWatchlistItem, updateWatchlistItem } from "../../services/memoryCenter";
import { listConversations } from "../../services/chat";

interface MemoryDrawerProps {
  open: boolean;
  onClose: () => void;
  userId: string;
  sessionId: string;
  onJumpToMessage?: (messageId: string) => void;
}

function formatTs(ts: string | null | undefined): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts);
  return d.toLocaleString();
}

export const MemoryDrawer: React.FC<MemoryDrawerProps> = ({ open, onClose, userId, sessionId, onJumpToMessage }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<MemoryDashboardResponse | null>(null);
  const [watchlistTitle, setWatchlistTitle] = useState("");
  const [watchlistAdding, setWatchlistAdding] = useState(false);
  const [watchlistView, setWatchlistView] = useState<"to_watch" | "watched" | "dismissed" | "deleted">("to_watch");
  const [watchlistQueryInput, setWatchlistQueryInput] = useState("");
  const [watchlistQuery, setWatchlistQuery] = useState("");
  const [watchlistItems, setWatchlistItems] = useState<WatchlistItemDto[]>([]);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [watchlistOffset, setWatchlistOffset] = useState(0);
  const [watchlistHasMore, setWatchlistHasMore] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editItem, setEditItem] = useState<WatchlistItemDto | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editYear, setEditYear] = useState<number | null>(null);
  const [explainOpen, setExplainOpen] = useState(false);
  const [explainItem, setExplainItem] = useState<WatchlistItemDto | null>(null);

  const tasteItems = useMemo(() => data?.taste_profile || [], [data]);
  const dashboardWatchlist = useMemo(() => data?.watchlist || [], [data]);

  const viewStatus: WatchlistStatus | undefined =
    watchlistView === "deleted" ? undefined : (watchlistView as WatchlistStatus);

  async function reloadWatchlist(reset: boolean) {
    if (!userId || !open) return;
    const limit = 50;
    const offset = reset ? 0 : watchlistOffset;
    setWatchlistLoading(true);
    try {
      const items = await listWatchlist({
        user_id: userId,
        status: viewStatus,
        query: watchlistQuery.trim() ? watchlistQuery.trim() : undefined,
        only_deleted: watchlistView === "deleted",
        include_deleted: watchlistView === "deleted",
        limit,
        offset,
      });
      const next = reset ? items : [...watchlistItems, ...items];
      setWatchlistItems(next);
      setWatchlistOffset(next.length);
      setWatchlistHasMore(items.length >= limit);
    } catch (e) {
      console.error("Failed to load watchlist", e);
      message.error(e instanceof Error ? e.message : "加载 Watchlist 失败");
      if (reset) {
        setWatchlistItems([]);
        setWatchlistOffset(0);
        setWatchlistHasMore(false);
      }
    } finally {
      setWatchlistLoading(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    if (!userId || !sessionId) {
      setData(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const conversations = await listConversations(userId, 100);
        const conv = conversations.find((c) => c.session_id === sessionId);
        if (!conv) {
          if (!cancelled) setData(null);
          return;
        }
        const resp = await getMemoryDashboard({ conversation_id: conv.id, user_id: userId });
        if (!cancelled) {
          setData(resp);
          // Bootstrap watchlist with the dashboard payload to avoid an empty flash.
          setWatchlistItems(resp.watchlist || []);
          setWatchlistOffset((resp.watchlist || []).length);
          setWatchlistHasMore((resp.watchlist || []).length >= 50);
        }
      } catch (e) {
        console.error("Failed to load memory dashboard", e);
        if (!cancelled) {
          setData(null);
          message.error(e instanceof Error ? e.message : "加载记忆中心失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, userId, sessionId]);

  useEffect(() => {
    if (!open || !userId) return;
    // When filters change, reload the watchlist.
    void reloadWatchlist(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, userId, watchlistView, watchlistQuery]);

  function statusLabel(s: string | undefined) {
    if (s === "watched") return "已看";
    if (s === "dismissed") return "不想看";
    return "待看";
  }

  function originLabel(s: string | undefined) {
    if (s === "assistant") return "助手回复";
    if (s === "user") return "用户输入";
    return "";
  }

  return (
    <Drawer title="记忆中心" open={open} onClose={onClose} width={520}>
      {loading ? (
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Card size="small">
            <Skeleton active paragraph={{ rows: 3 }} />
          </Card>
          <Card size="small">
            <Skeleton active paragraph={{ rows: 4 }} />
          </Card>
        </Space>
      ) : !data ? (
        <Empty description="暂无记忆数据（新会话或尚未生成摘要/记忆）" />
      ) : (
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Card size="small" title="前情提要（会话摘要）">
            {data.summary?.content?.trim() ? (
              <>
                <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>
                  {data.summary.content}
                </Typography.Paragraph>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  更新时间：{formatTs(data.summary.updated_at)}
                </Typography.Text>
              </>
            ) : (
              <Typography.Text type="secondary">暂无摘要（对话足够长后会自动生成）</Typography.Text>
            )}
          </Card>

          <Card
            size="small"
            title={
              <span>
                Taste DNA（长期记忆）{" "}
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {data.stats?.total_memories ?? tasteItems.length} 条
                </Typography.Text>
              </span>
            }
          >
            {tasteItems.length === 0 ? (
              <Typography.Text type="secondary">暂无长期记忆（需要产生可抽取的偏好/事实/约束）</Typography.Text>
            ) : (
              <Space wrap size={[8, 8]}>
                {tasteItems.map((it) => (
                  <Tag key={it.id}>
                    <span>{it.tag || it.id}</span>
                    <Popconfirm
                      title="忘掉这条记忆？"
                      okText="删除"
                      cancelText="取消"
                      onConfirm={async () => {
                        try {
                          await deleteMemoryItem({ memory_id: it.id, user_id: userId });
                          setData((prev) => {
                            if (!prev) return prev;
                            return {
                              ...prev,
                              taste_profile: prev.taste_profile.filter((x) => x.id !== it.id),
                              stats: {
                                ...prev.stats,
                                total_memories: Math.max(0, (prev.stats?.total_memories ?? 0) - 1),
                              },
                            };
                          });
                          message.success("已删除");
                        } catch (e) {
                          message.error(e instanceof Error ? e.message : "删除失败");
                        }
                      }}
                    >
                      <span
                        style={{ marginLeft: 6, cursor: "pointer", color: "rgba(0,0,0,0.45)" }}
                        onClick={(e) => e.stopPropagation()}
                        aria-label="delete memory"
                      >
                        <CloseOutlined />
                      </span>
                    </Popconfirm>
                  </Tag>
                ))}
              </Space>
            )}

            <div style={{ marginTop: 12 }}>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                删除会同步影响推荐与记忆召回（仅影响长期记忆，不影响会话摘要）。
              </Typography.Text>
            </div>
          </Card>

          <Card
            size="small"
            title={
              <span>
                Watchlist（想看清单）{" "}
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {data.stats?.watchlist_count ?? dashboardWatchlist.length} 条
                </Typography.Text>
              </span>
            }
            extra={
              <Button
                size="small"
                onClick={async () => {
                  try {
                    const resp = await dedupMergeWatchlist({ user_id: userId });
                    message.success(
                      `已去重合并：kept=${resp.result?.kept ?? 0}, deleted=${resp.result?.deleted ?? 0}, merged=${resp.result?.merged ?? 0}`,
                    );
                    await reloadWatchlist(true);
                  } catch (e) {
                    message.error(e instanceof Error ? e.message : "去重合并失败");
                  }
                }}
              >
                去重合并
              </Button>
            }
          >
            <div style={{ marginBottom: 12 }}>
              <Space direction="vertical" style={{ width: "100%" }} size={8}>
                <Segmented
                  options={[
                    { label: "待看", value: "to_watch" },
                    { label: "已看", value: "watched" },
                    { label: "不想看", value: "dismissed" },
                    { label: "已删除", value: "deleted" },
                  ]}
                  value={watchlistView}
                  onChange={(v) => setWatchlistView(v as any)}
                />
                <Space.Compact style={{ width: "100%" }}>
                  <Input
                    placeholder="搜索标题"
                    value={watchlistQueryInput}
                    onChange={(e) => setWatchlistQueryInput(e.target.value)}
                    onPressEnter={() => setWatchlistQuery(watchlistQueryInput.trim())}
                    allowClear
                  />
                  <Button onClick={() => setWatchlistQuery(watchlistQueryInput.trim())}>搜索</Button>
                </Space.Compact>
              </Space>
            </div>

            <Space.Compact style={{ width: "100%" }}>
              <Input
                placeholder="输入电影名，加入想看清单"
                value={watchlistTitle}
                onChange={(e) => setWatchlistTitle(e.target.value)}
                onPressEnter={async () => {
                  const title = watchlistTitle.trim();
                  if (!title || watchlistAdding) return;
                  setWatchlistAdding(true);
                  try {
                    const created = await addWatchlistItem({ user_id: userId, title });
                    // Keep dashboard data best-effort updated.
                    setData((prev) => {
                      if (!prev) return prev;
                      return {
                        ...prev,
                        watchlist: [created, ...(prev.watchlist || [])],
                        stats: {
                          ...prev.stats,
                          watchlist_count: (prev.stats?.watchlist_count ?? 0) + 1,
                        },
                      };
                    });
                    setWatchlistTitle("");
                    message.success("已加入 Watchlist");
                    await reloadWatchlist(true);
                  } catch (e) {
                    message.error(e instanceof Error ? e.message : "加入失败");
                  } finally {
                    setWatchlistAdding(false);
                  }
                }}
                disabled={watchlistAdding}
              />
              <Button
                type="primary"
                loading={watchlistAdding}
                onClick={async () => {
                  const title = watchlistTitle.trim();
                  if (!title || watchlistAdding) return;
                  setWatchlistAdding(true);
                  try {
                    const created = await addWatchlistItem({ user_id: userId, title });
                    setData((prev) => {
                      if (!prev) return prev;
                      return {
                        ...prev,
                        watchlist: [created, ...(prev.watchlist || [])],
                        stats: {
                          ...prev.stats,
                          watchlist_count: (prev.stats?.watchlist_count ?? 0) + 1,
                        },
                      };
                    });
                    setWatchlistTitle("");
                    message.success("已加入 Watchlist");
                    await reloadWatchlist(true);
                  } catch (e) {
                    message.error(e instanceof Error ? e.message : "加入失败");
                  } finally {
                    setWatchlistAdding(false);
                  }
                }}
                disabled={!watchlistTitle.trim()}
              >
                加入
              </Button>
            </Space.Compact>

            <div style={{ marginTop: 12 }}>
              {watchlistLoading ? (
                <Skeleton active paragraph={{ rows: 4 }} />
              ) : watchlistItems.length === 0 ? (
                <Typography.Text type="secondary">
                  暂无条目（可手动添加；自动捕获会在对话回合结束后写入）
                </Typography.Text>
              ) : (
                <Space direction="vertical" style={{ width: "100%" }} size={6}>
                  {watchlistItems.map((it) => (
                    <div
                      key={it.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 8,
                        padding: "6px 8px",
                        border: "1px solid rgba(0,0,0,0.06)",
                        borderRadius: 6,
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <Space size={6}>
                          <Typography.Text ellipsis style={{ maxWidth: 360 }}>
                            {it.title}
                            {it.year ? ` (${it.year})` : ""}
                          </Typography.Text>
                          {it.deleted_at ? <Tag color="default">已删除</Tag> : <Tag>{statusLabel(it.status)}</Tag>}
                          {(it.source || it.metadata?.source) === "auto_capture" ? (
                            <Tag color="blue">自动</Tag>
                          ) : null}
                        </Space>
                      </div>
                      <Space size={4}>
                        {!it.deleted_at ? (
                          <>
                            <Button
                              size="small"
                              onClick={() => {
                                setEditItem(it);
                                setEditTitle(it.title || "");
                                setEditYear(typeof it.year === "number" ? it.year : null);
                                setEditOpen(true);
                              }}
                            >
                              编辑
                            </Button>
                            {it.status !== "watched" ? (
                              <Button
                                size="small"
                                onClick={async () => {
                                  try {
                                    await updateWatchlistItem({ user_id: userId, item_id: it.id, status: "watched" });
                                    message.success("已标记为已看");
                                    await reloadWatchlist(true);
                                  } catch (e) {
                                    message.error(e instanceof Error ? e.message : "更新失败");
                                  }
                                }}
                              >
                                已看
                              </Button>
                            ) : (
                              <Button
                                size="small"
                                onClick={async () => {
                                  try {
                                    await updateWatchlistItem({ user_id: userId, item_id: it.id, status: "to_watch" });
                                    message.success("已恢复为待看");
                                    await reloadWatchlist(true);
                                  } catch (e) {
                                    message.error(e instanceof Error ? e.message : "更新失败");
                                  }
                                }}
                              >
                                待看
                              </Button>
                            )}
                            {it.status !== "dismissed" ? (
                              <Button
                                size="small"
                                onClick={async () => {
                                  try {
                                    await updateWatchlistItem({ user_id: userId, item_id: it.id, status: "dismissed" });
                                    message.success("已标记为不想看");
                                    await reloadWatchlist(true);
                                  } catch (e) {
                                    message.error(e instanceof Error ? e.message : "更新失败");
                                  }
                                }}
                              >
                                不想看
                              </Button>
                            ) : (
                              <Button
                                size="small"
                                onClick={async () => {
                                  try {
                                    await updateWatchlistItem({ user_id: userId, item_id: it.id, status: "to_watch" });
                                    message.success("已恢复为待看");
                                    await reloadWatchlist(true);
                                  } catch (e) {
                                    message.error(e instanceof Error ? e.message : "更新失败");
                                  }
                                }}
                              >
                                待看
                              </Button>
                            )}
                            <Popconfirm
                              title="从 Watchlist 移除？"
                              okText="移除"
                              cancelText="取消"
                              onConfirm={async () => {
                                try {
                                  await deleteWatchlistItem({ user_id: userId, item_id: it.id });
                                  setData((prev) => {
                                    if (!prev) return prev;
                                    return {
                                      ...prev,
                                      watchlist: (prev.watchlist || []).filter((x) => x.id !== it.id),
                                      stats: {
                                        ...prev.stats,
                                        watchlist_count: Math.max(0, (prev.stats?.watchlist_count ?? 0) - 1),
                                      },
                                    };
                                  });
                                  message.success("已移除");
                                  await reloadWatchlist(true);
                                } catch (e) {
                                  message.error(e instanceof Error ? e.message : "移除失败");
                                }
                              }}
                            >
                              <Button size="small" type="text" icon={<CloseOutlined />} aria-label="remove" />
                            </Popconfirm>
                            {(it.source || it.metadata?.source) === "auto_capture" ? (
                              <Button
                                size="small"
                                onClick={() => {
                                  setExplainItem(it);
                                  setExplainOpen(true);
                                }}
                              >
                                来源
                              </Button>
                            ) : null}
                          </>
                        ) : (
                          <Button
                            size="small"
                            onClick={async () => {
                              try {
                                await restoreWatchlistItem({ user_id: userId, item_id: it.id });
                                message.success("已恢复");
                                await reloadWatchlist(true);
                              } catch (e) {
                                message.error(e instanceof Error ? e.message : "恢复失败");
                              }
                            }}
                          >
                            恢复
                          </Button>
                        )}
                      </Space>
                    </div>
                  ))}
                  {watchlistHasMore ? (
                    <Button
                      block
                      loading={watchlistLoading}
                      onClick={async () => {
                        await reloadWatchlist(false);
                      }}
                    >
                      加载更多
                    </Button>
                  ) : null}
                </Space>
              )}
            </div>
          </Card>
        </Space>
      )}

      <Modal
        title="编辑 Watchlist"
        open={editOpen}
        okText="保存"
        cancelText="取消"
        onCancel={() => setEditOpen(false)}
        onOk={async () => {
          if (!editItem) return;
          const title = editTitle.trim();
          if (!title) {
            message.error("标题不能为空");
            return;
          }
          try {
            await updateWatchlistItem({
              user_id: userId,
              item_id: editItem.id,
              title,
              year: editYear ?? undefined,
            });
            message.success("已保存");
            setEditOpen(false);
            await reloadWatchlist(true);
          } catch (e) {
            message.error(e instanceof Error ? e.message : "保存失败");
          }
        }}
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} placeholder="电影名" />
          <InputNumber
            style={{ width: "100%" }}
            value={editYear}
            onChange={(v) => setEditYear(typeof v === "number" ? v : null)}
            placeholder="年份（可选）"
            min={1880}
            max={2100}
          />
        </Space>
      </Modal>

      <Modal
        title="为什么会自动加入？"
        open={explainOpen}
        okText="知道了"
        cancelText="关闭"
        onCancel={() => setExplainOpen(false)}
        onOk={() => setExplainOpen(false)}
      >
        {explainItem ? (
          <Space direction="vertical" style={{ width: "100%" }} size={8}>
            <Typography.Text>
              标题：{explainItem.title}
              {explainItem.year ? ` (${explainItem.year})` : ""}
            </Typography.Text>
            <Typography.Text type="secondary">
              触发：{explainItem.capture_trigger || explainItem.metadata?.capture_trigger || "-"}
              {originLabel(explainItem.capture_origin || explainItem.metadata?.capture_origin)
                ? ` / 来源：${originLabel(explainItem.capture_origin || explainItem.metadata?.capture_origin)}`
                : ""}
            </Typography.Text>
            {(explainItem.capture_evidence || explainItem.metadata?.capture_evidence) ? (
              <Card size="small" title="证据片段">
                <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                  {String(explainItem.capture_evidence || explainItem.metadata?.capture_evidence || "")}
                </Typography.Paragraph>
              </Card>
            ) : null}
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              conversation_id: {String(explainItem.conversation_id || explainItem.metadata?.conversation_id || "-")}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              user_message_id: {String(explainItem.user_message_id || explainItem.metadata?.user_message_id || "-")}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              assistant_message_id:{" "}
              {String(explainItem.assistant_message_id || explainItem.metadata?.assistant_message_id || "-")}
            </Typography.Text>
            {onJumpToMessage ? (
              <Space wrap>
                {(explainItem.user_message_id || explainItem.metadata?.user_message_id) ? (
                  <Button
                    size="small"
                    onClick={() => {
                      const id = String(explainItem.user_message_id || explainItem.metadata?.user_message_id || "");
                      if (!id) return;
                      setExplainOpen(false);
                      onClose();
                      setTimeout(() => onJumpToMessage(id), 50);
                    }}
                  >
                    跳到用户消息
                  </Button>
                ) : null}
                {(explainItem.assistant_message_id || explainItem.metadata?.assistant_message_id) ? (
                  <Button
                    size="small"
                    onClick={() => {
                      const id = String(explainItem.assistant_message_id || explainItem.metadata?.assistant_message_id || "");
                      if (!id) return;
                      setExplainOpen(false);
                      onClose();
                      setTimeout(() => onJumpToMessage(id), 50);
                    }}
                  >
                    跳到助手消息
                  </Button>
                ) : null}
              </Space>
            ) : null}
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              提示：你可以点击“移除”来撤销这条自动加入；未来可以进一步支持“本回合一键撤销”。
            </Typography.Text>
          </Space>
        ) : null}
      </Modal>
    </Drawer>
  );
};
