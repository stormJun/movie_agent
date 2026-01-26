import { useEffect, useMemo, useRef, useState } from "react";
import { MenuFoldOutlined, MenuUnfoldOutlined, ArrowUpOutlined, SettingOutlined, BugOutlined, MessageOutlined, ProjectOutlined, FileTextOutlined, UserOutlined, RobotOutlined, CopyOutlined, LikeOutlined, DislikeOutlined, ReloadOutlined, DownOutlined, VideoCameraOutlined } from "@ant-design/icons";
import CodeBlock from "../components/CodeBlock";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  Divider,
  Drawer,
  Dropdown,
  Flex,
  Input,
  Layout,
  Progress,
  Radio,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentType, DebugData, StreamEvent } from "../types/chat";
import {
  chat,
  chatStream,
  clearChat,
  getDebugData,
  getExampleQuestions,
  getMessages,
  type MessageItem,
} from "../services/chat";
import { getKnowledgeGraphFromMessage } from "../services/graph";
import type { KnowledgeGraphResponse } from "../types/graph";
import { getSourceContent, getSourceInfoBatch } from "../services/source";
import { sendFeedback } from "../services/feedback";
import { deleteWatchlistItem } from "../services/memoryCenter";
import { KnowledgeGraphPanel } from "../components/KnowledgeGraphPanel";
import { SessionList } from "../components/SessionList";
import DebugDrawer from "../components/debug/DebugDrawer";
import { MemoryDrawer } from "../components/memory-center/MemoryDrawer";
import "../styles/debug.css";

type Role = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  query?: string;
  // Langfuse trace id (aka request_id from /api/v1/chat/stream) for this assistant response.
  requestId?: string;
  sourceIds?: string[];
  kgData?: KnowledgeGraphResponse;
  reference?: unknown;
  rawThinking?: string;
};

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function newSessionId(): string {
  return globalThis.crypto?.randomUUID?.() ?? String(Date.now());
}

function loadOrCreateSessionId(storageKey: string): string {
  const existing = localStorage.getItem(storageKey);
  if (existing) return existing;
  const next = newSessionId();
  localStorage.setItem(storageKey, next);
  return next;
}

function usePersistentSessionId(scopeKey: string) {
  const storageKey = `graphrag.sessionId.${scopeKey || "default"}`;
  const [sessionId, setSessionId] = useState<string>(() =>
    loadOrCreateSessionId(storageKey),
  );

  useEffect(() => {
    setSessionId(loadOrCreateSessionId(storageKey));
  }, [storageKey]);

  const set = (id: string) => {
    localStorage.setItem(storageKey, id);
    setSessionId(id);
  };

  const rotate = () => {
    const next = newSessionId();
    set(next);
  };

  return { sessionId, setSessionId: set, rotate };
}

function loadOrCreateUserId(storageKey: string): string {
  const existing = localStorage.getItem(storageKey);
  if (existing) return existing;
  const next = "u1";
  localStorage.setItem(storageKey, next);
  return next;
}

function usePersistentUserId(scopeKey: string) {
  const storageKey = `graphrag.userId.${scopeKey || "default"}`;
  const [userId, setUserId] = useState<string>(() => loadOrCreateUserId(storageKey));

  useEffect(() => {
    setUserId(loadOrCreateUserId(storageKey));
  }, [storageKey]);

  const update = (next: string) => {
    const trimmed = (next || "").trim();
    localStorage.setItem(storageKey, trimmed);
    setUserId(trimmed);
  };

  return { userId, setUserId: update };
}

const agentOptions: Array<{ label: string; value: AgentType }> = [
  { label: "Graph Agent", value: "graph_agent" },
  { label: "Hybrid Agent", value: "hybrid_agent" },
  { label: "Naive RAG", value: "naive_rag_agent" },
  { label: "Deep Research", value: "deep_research_agent" },
  { label: "Fusion Agent", value: "fusion_agent" },
];

function extractSourceIds(answer: string): string[] {
  const ids: string[] = [];
  const chunksPattern = /Chunks':\s*\[([^\]]*)\]/g;
  const matches = [...answer.matchAll(chunksPattern)];
  for (const m of matches) {
    const inner = m[1] || "";
    const quoted = [...inner.matchAll(/'([^']*)'/g)].map((x) => x[1]).filter(Boolean);
    if (quoted.length) {
      ids.push(...quoted);
      continue;
    }
    const parts = inner.split(",").map((s) => s.trim()).filter(Boolean);
    ids.push(...parts);
  }
  return Array.from(new Set(ids));
}

export function ChatPage() {
  const { sessionId, setSessionId, rotate } = usePersistentSessionId("default");
  const { userId, setUserId } = usePersistentUserId("default");

  // Feature Navigation State
  const [activeFeature, setActiveFeature] = useState<"chat" | "kg" | "sources" | "settings">("chat");

  const [agentType, setAgentType] = useState<AgentType>("hybrid_agent");
  // Default to debug-on for easier inspection during development.
  const [debugMode, setDebugMode] = useState<boolean>(true);
  const [useStream, setUseStream] = useState<boolean>(true);
  const [useDeeperTool, setUseDeeperTool] = useState<boolean>(true);
  const [showThinking, setShowThinking] = useState<boolean>(false);
  const [useChainExploration, setUseChainExploration] = useState<boolean>(true);

  // Privacy & Memory Settings
  const [isIncognito, setIsIncognito] = useState<boolean>(() => {
    return localStorage.getItem("graphrag.privacy.incognito") === "true";
  });
  const [autoCaptureEnabled, setAutoCaptureEnabled] = useState<boolean>(() => {
    const val = localStorage.getItem("graphrag.privacy.autoCapture");
    return val !== "false"; // Default true
  });

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [executionLogs, setExecutionLogs] = useState<unknown[]>([]);
  const [latestDebugData, setLatestDebugData] = useState<DebugData | null>(null);
  const [debugDrawerOpen, setDebugDrawerOpen] = useState(false);
  const [memoryDrawerOpen, setMemoryDrawerOpen] = useState(false);
  const [iterations, setIterations] = useState<unknown[]>([]);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [processingStage, setProcessingStage] = useState<string>("");
  const [processingPercent, setProcessingPercent] = useState<number>(0);
  const [exampleQuestions, setExampleQuestions] = useState<string[]>([]);

  useEffect(() => {
    getExampleQuestions()
      .then(setExampleQuestions)
      .catch((e) => {
        console.warn("Failed to load examples", e);
        setExampleQuestions([]);
      });
  }, []);

  console.log("Messages length:", messages.length);
  const [retrievalProgress, setRetrievalProgress] = useState<
    Record<string, { retrievalCount?: number; error?: string }>
  >({});
  const [kgData, setKgData] = useState<KnowledgeGraphResponse | null>(null);
  const [reference, setReference] = useState<unknown>(null);
  const [rawThinking, setRawThinking] = useState<string>("");
  const [debugTabKey, setDebugTabKey] = useState<string>("logs");
  const [feedbackState, setFeedbackState] = useState<Record<string, "positive" | "negative">>(
    {},
  );
  const [feedbackPending, setFeedbackPending] = useState<Record<string, boolean>>({});
  const [perfEvents, setPerfEvents] = useState<
    Array<{ op: string; ms: number; ts: number }>
  >([]);
  const [highlightMessageId, setHighlightMessageId] = useState<string | null>(null);

  function notifyWatchlistAutoCapture(added: Array<Record<string, unknown>>) {
    if (!added?.length) return;
    const titles = added
      .map((x) => (typeof x.title === "string" ? x.title : ""))
      .filter(Boolean)
      .slice(0, 5);
    const extra = added.length > titles.length ? ` 等${added.length}部` : "";
    const msgKey = `watchlist_auto_capture.${Date.now()}`;

    message.open({
      key: msgKey,
      type: "info",
      duration: 6,
      content: (
        <Space>
          <span>
            已自动加入 Watchlist：{titles.join("、")}
            {extra}
          </span>
          <Button
            size="small"
            onClick={async () => {
              const ids = added
                .map((x) => (typeof x.id === "string" ? x.id : ""))
                .filter(Boolean);
              if (!ids.length) return;
              try {
                await Promise.all(ids.map((id) => deleteWatchlistItem({ user_id: userId, item_id: id })));
                message.success("已撤销本次加入");
                message.destroy(msgKey);
              } catch (e) {
                message.error(e instanceof Error ? e.message : "撤销失败");
              }
            }}
          >
            撤销
          </Button>
        </Space>
      ),
    });
  }

  async function jumpToMessage(messageId: string) {
    const targetId = (messageId || "").trim();
    if (!targetId) return;

    setActiveFeature("chat");

    const exists = messages.some((m) => m.id === targetId);
    if (!exists) {
      try {
        const history = await getMessages(userId, sessionId);
        const restoredMessages: ChatMessage[] = [];
        for (let i = 0; i < history.length; i++) {
          const item = history[i];
          const role = item.role as Role;
          let query = undefined;
          if (role === "assistant") {
            for (let j = i - 1; j >= 0; j--) {
              if (history[j].role === "user") {
                query = history[j].content;
                break;
              }
            }
          }
          restoredMessages.push({
            id: item.id,
            role: role,
            content: item.content,
            createdAt: new Date(item.created_at).getTime(),
            query,
            sourceIds: extractSourceIds(item.content),
          });
        }
        setMessages(restoredMessages);
      } catch (e) {
        message.warning("未能加载历史消息以定位该条目");
      }
    }

    setTimeout(() => {
      const el = document.getElementById(`message-${targetId}`);
      if (!el) {
        message.warning("未在当前会话中找到对应消息（可能已清空或未落库）");
        return;
      }
      setHighlightMessageId(targetId);
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => setHighlightMessageId((prev) => (prev === targetId ? null : prev)), 2500);
    }, 80);
  }

  const [sourceDrawerOpen, setSourceDrawerOpen] = useState(false);
  const [sourceDrawerTitle, setSourceDrawerTitle] = useState<string>("");
  const [sourceDrawerContent, setSourceDrawerContent] = useState<string>("");
  const [sourceDrawerLoading, setSourceDrawerLoading] = useState(false);

  const [sourceInfoMap, setSourceInfoMap] = useState<Record<string, string>>({});

  // Layout resize state
  const [sessionListWidth, setSessionListWidth] = useState(260);
  const [sessionListVisible, setSessionListVisible] = useState(true);
  const [chatSideWidth, setChatSideWidth] = useState(320);
  const isResizingRef = useRef<"left" | "right" | null>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingRef.current) return;
      e.preventDefault();
      if (isResizingRef.current === "left") {
        setSessionListWidth((prev) => Math.max(200, Math.min(600, e.clientX)));
      } else if (isResizingRef.current === "right") {
        setChatSideWidth((prev) => Math.max(240, Math.min(600, window.innerWidth - e.clientX)));
      }
    };
    const handleMouseUp = () => {
      if (isResizingRef.current) {
        isResizingRef.current = null;
        document.body.style.cursor = "default";
        document.body.style.userSelect = "auto";
      }
    };
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  const handleResizeStart = (direction: "left" | "right") => {
    isResizingRef.current = direction;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  };

  // 输入框内容，避免依赖 Form 内部状态，降低循环引用警告
  const [promptValue, setPromptValue] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Debug mode supports streaming; debug data is fetched separately via /api/v1/debug/{request_id}.
  // Debug mode requires streaming so we can fetch the separated debug payload
  // via GET /api/v1/debug/{request_id} after the stream ends.
  const canStream = useMemo(() => useStream || debugMode, [useStream, debugMode]);
  const retrievalEntries = Object.entries(retrievalProgress);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages.length]);

  async function handleClear(clearBackend = false) {
    try {
      if (clearBackend && userId.trim()) {
        await clearChat(userId, sessionId);
      }
    } catch {
      // 后端清空失败不影响前端清空
    }
    setMessages([]);
    setExecutionLogs([]);
    setIterations([]);
    setKgData(null);
    setReference(null);
    setRawThinking("");
    setDebugTabKey("logs");
    setFeedbackState({});
    setFeedbackPending({});
    setPromptValue("");
    setProcessingPercent(0);
    setRetrievalProgress({});
  }

  async function handleRegenerate() {
    if (isSending) return;

    // Find the last user message query
    let lastUserQuery = "";
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        lastUserQuery = messages[i].content;
        break;
      }
    }

    if (!lastUserQuery) {
      message.warning("No previous query found");
      return;
    }

    // Remove the last assistant message
    const newMessages = messages.filter((_, idx) => idx !== messages.length - 1);
    setMessages(newMessages);

    // Resend the query
    setPromptValue(lastUserQuery);
    // Wait a tick for the state to update, then call handleSend
    setTimeout(() => handleSend(), 0);
  }

  async function handleNewSession() {
    rotate();
    // handleClear 會依賴 sessionId 變更後的 effect 嗎？
    // rotate 更新了 sessionId，UI 重繪。
    // 但 handleClear 清空 messages 是即時的。
    // 新的 sessionId 會是空的，所以 messages 也該清空。
    await handleClear(false);
  }

  async function handleSelectSession(sid: string) {
    if (sid === sessionId) return;
    setSessionId(sid);
    await handleClear(false); // 清理当前状态

    // 加载历史消息
    try {
      const history = await getMessages(userId, sid);
      const restoredMessages: ChatMessage[] = [];
      for (let i = 0; i < history.length; i++) {
        const item = history[i];
        const role = item.role as Role;
        let query = undefined;
        // 如果是 assistant 消息，尝试回溯找最近一条 user 消息作为 query
        if (role === "assistant") {
          for (let j = i - 1; j >= 0; j--) {
            if (history[j].role === "user") {
              query = history[j].content;
              break;
            }
          }
        }

        restoredMessages.push({
          id: item.id,
          role: role,
          content: item.content,
          createdAt: new Date(item.created_at).getTime(),
          query,
          sourceIds: extractSourceIds(item.content),
        });
      }
      setMessages(restoredMessages);
    } catch (e) {
      message.error("加载历史消息失败");
    }
  }

  async function handleStop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsSending(false);
    setProcessingStage("");
    setProcessingPercent(0);
    setRetrievalProgress({});
  }

  async function handleSend() {
    const prompt = (promptValue || "").trim();
    if (!prompt) return;
    if (!userId.trim()) {
      message.warning("请先填写 user_id");
      return;
    }

    const userMsg: ChatMessage = {
      id: newSessionId(),
      role: "user",
      content: prompt,
      createdAt: Date.now(),
    };

    const assistantMsgId = newSessionId();
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      createdAt: Date.now(),
      query: prompt,
      rawThinking: "",
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsSending(true);
    setExecutionLogs([]);
    setLatestDebugData(null);
    setIterations([]);
    setKgData(null);
    setReference(null);
    setRawThinking("");
    setDebugTabKey("logs");
    setProcessingStage("准备发送请求...");
    setProcessingPercent(5);
    setPromptValue("");
    setRetrievalProgress({});

    const req = {
      message: prompt,
      user_id: userId,
      session_id: sessionId,
      kb_prefix: "movie", // Set knowledge base prefix for movie queries
      debug: debugMode,
      agent_type: agentType,
      use_deeper_tool: agentType === "deep_research_agent" ? useDeeperTool : undefined,
      show_thinking: agentType === "deep_research_agent" ? showThinking : undefined,
      use_chain_exploration: agentType === "fusion_agent" ? useChainExploration : undefined,
      incognito: isIncognito,
      watchlist_auto_capture: autoCaptureEnabled,
    };

    const updateAssistant = (delta: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId ? { ...m, content: m.content + delta } : m,
        ),
      );
    };

    const updateAssistantThinking = (delta: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? { ...m, rawThinking: `${m.rawThinking || ""}${delta}` }
            : m,
        ),
      );
    };

    try {
      const t0 = performanceNow();
      if (!canStream) {
        setProcessingStage("发送请求到服务器...");
        setProcessingPercent(15);
        const resp = await chat(req);
        setProcessingStage("处理响应...");
        setProcessingPercent(80);
        updateAssistant(resp.answer || "");
        if (resp.execution_log) setExecutionLogs(resp.execution_log);
        if (debugMode && !resp.execution_log) {
          const merged: unknown[] = [];
          if (resp.route_decision) {
            merged.push({ node: "route_decision", output: resp.route_decision });
          }
          if (Array.isArray(resp.rag_runs) && resp.rag_runs.length) {
            merged.push(...resp.rag_runs);
          }
          if (merged.length) setExecutionLogs(merged);
        }
        if (resp.iterations) setIterations(resp.iterations);
        if (resp.kg_data) {
          const nextKg = resp.kg_data as unknown as KnowledgeGraphResponse;
          setKgData(nextKg);
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, kgData: nextKg } : m)),
          );
        }
        if (resp.reference) setReference(resp.reference);
        if (typeof resp.raw_thinking === "string" && resp.raw_thinking.trim()) {
          setRawThinking(resp.raw_thinking);
          updateAssistantThinking(resp.raw_thinking);
        }
        const extraExecutionLogs = resp.execution_logs;
        if (Array.isArray(extraExecutionLogs) && extraExecutionLogs.length) {
          setExecutionLogs((prev) => [...prev, ...extraExecutionLogs]);
        }

        const sourceIds = extractSourceIds(resp.answer || "");
        if (sourceIds.length) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, sourceIds } : m,
            ),
          );
          void primeSourceInfo(sourceIds);
        }

        // Streamlit parity: in debug mode, try to auto-extract KG for non-deep agents.
        if (debugMode && agentType !== "deep_research_agent") {
          try {
            const existing = resp.kg_data as unknown as KnowledgeGraphResponse | undefined;
            if (existing?.nodes?.length) {
              setDebugTabKey("kg");
            } else {
              const extracted = await getKnowledgeGraphFromMessage({ message: resp.answer || "", query: prompt });
              if (extracted?.nodes?.length) {
                setKgData(extracted);
                setMessages((prev) =>
                  prev.map((m) => (m.id === assistantMsgId ? { ...m, kgData: extracted } : m)),
                );
                setDebugTabKey("kg");
              }
            }
          } catch {
            // ignore
          }
        }

        setPerfEvents((prev) => [
          ...prev,
          { op: "chat", ms: performanceNow() - t0, ts: Date.now() },
        ]);

        const added = (resp as any)?.watchlist_auto_capture?.added;
        if (Array.isArray(added) && added.length) {
          notifyWatchlistAutoCapture(added as Array<Record<string, unknown>>);
        }

        setIsSending(false);
        setProcessingStage("");
        setProcessingPercent(0);
        setRetrievalProgress({});
        return;
      }

      setProcessingStage("建立流式连接...");
      setProcessingPercent(15);
      const controller = new AbortController();
      abortRef.current = controller;

      let firstTokenReceived = false;
      let streamRequestId: string | null = null;
      const onEvent = (ev: StreamEvent) => {
        // Compatibility: some backends incorrectly wrap JSON as token content.
        if (ev.status === "token" && typeof ev.content === "string") {
          if (!firstTokenReceived) {
            setProcessingStage("接收响应...");
            setProcessingPercent(90);
            firstTokenReceived = true;
          }
          const raw = ev.content.trim();
          if (raw.startsWith("{") && raw.endsWith("}")) {
            try {
              const nested = JSON.parse(raw) as StreamEvent;
              if (nested && typeof nested === "object" && "status" in nested) {
                onEvent(nested);
                return;
              }
            } catch {
              // ignore
            }
          }
        }

        if (ev.status === "progress") {
          const content =
            ev.content && typeof ev.content === "object"
              ? (ev.content as Record<string, unknown>)
              : {};
          const stage = typeof content.stage === "string" ? content.stage : "progress";
          const agentType =
            typeof content.agent_type === "string" ? content.agent_type : "";
          const retrievalCount =
            typeof content.retrieval_count === "number" ? content.retrieval_count : null;
          const completed =
            typeof content.completed === "number" ? content.completed : null;
          const total = typeof content.total === "number" ? content.total : null;
          const error = typeof content.error === "string" ? content.error : "";
          let label = "处理中";
          if (stage === "retrieval") label = "检索中";
          if (stage === "generation") label = "生成中";
          if (agentType) label += ` (${agentType})`;
          if (retrievalCount !== null) label += `，命中 ${retrievalCount}`;
          if (total && completed !== null) label += `，进度 ${completed}/${total}`;
          if (error) label += "，检索异常";
          setProcessingStage(label);
          if (stage === "retrieval" && agentType) {
            setRetrievalProgress((prev) => ({
              ...prev,
              [agentType]: {
                retrievalCount: retrievalCount ?? prev[agentType]?.retrievalCount,
                error: error || prev[agentType]?.error,
              },
            }));
          }
          if (total && completed !== null) {
            const ratio = Math.min(Math.max(completed / total, 0), 1);
            const nextPercent = Math.min(85, Math.round(ratio * 80));
            setProcessingPercent((prev) => Math.max(prev, nextPercent));
          } else {
            setProcessingPercent((prev) => Math.max(prev, 30));
          }
          return;
        }
        if (ev.status === "start") {
          if (typeof ev.request_id === "string" && ev.request_id.trim()) {
            streamRequestId = ev.request_id;
          }
          return;
        }
        if (ev.status === "token") {
          updateAssistant(String(ev.content || ""));
          return;
        }
        if (ev.status === "thinking") {
          const chunk = String((ev as { content?: unknown }).content || "");
          if (chunk) {
            setRawThinking((prev) => `${prev}${chunk}`);
            updateAssistantThinking(chunk);
          }
          return;
        }
        if (ev.status === "execution_log") {
          setExecutionLogs((prev) => [...prev, ev.content]);
          return;
        }
        if (ev.status === "execution_logs") {
          if (Array.isArray(ev.content)) setExecutionLogs(ev.content as unknown[]);
          return;
        }
        if (ev.status === "watchlist_auto_capture") {
          const content = (ev as { content?: unknown }).content;
          const added = isPlainRecord(content) ? (content as any).added : null;
          if (Array.isArray(added) && added.length) {
            notifyWatchlistAutoCapture(added as Array<Record<string, unknown>>);
          }
          return;
        }
        if (ev.status === "done") {
          setProcessingStage("完成");
          setProcessingPercent(100);
          if (!streamRequestId && typeof ev.request_id === "string" && ev.request_id.trim()) {
            streamRequestId = ev.request_id;
          }
          if (streamRequestId) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, requestId: streamRequestId! } : m,
              ),
            );
          }
          const doneThinking =
            typeof (ev as { thinking_content?: unknown }).thinking_content === "string"
              ? String((ev as { thinking_content?: string }).thinking_content)
              : "";
          if (doneThinking.trim()) {
            setRawThinking(doneThinking);
            updateAssistantThinking(doneThinking);
          }
          if (debugMode && streamRequestId) {
            void (async () => {
              try {
                const debugData = await getDebugData({
                  request_id: streamRequestId!,
                  user_id: userId,
                  session_id: sessionId,
                });
                setLatestDebugData(debugData);
                if (Array.isArray(debugData.execution_log)) {
                  setExecutionLogs(debugData.execution_log as unknown[]);
                }
                // Make debug info discoverable; users often won't be on the Settings tab.
                setDebugDrawerOpen(true);
              } catch (e) {
                console.warn("Failed to fetch debug data", e);
              }
            })();
          }
          setIsSending(false);
          setProcessingStage("");
          setProcessingPercent(0);
          setRetrievalProgress({});
          abortRef.current = null;
          return;
        }
        if (ev.status === "error") {
          setIsSending(false);
          setProcessingStage("");
          setProcessingPercent(0);
          setRetrievalProgress({});
          abortRef.current = null;
          const errorMessage =
            typeof (ev as { message?: unknown }).message === "string"
              ? (ev as { message?: string }).message
              : "流式输出发生错误";
          message.error(errorMessage);
        }
      };

      await chatStream(req, onEvent, { signal: controller.signal });
      setPerfEvents((prev) => [
        ...prev,
        { op: "chat_stream", ms: performanceNow() - t0, ts: Date.now() },
      ]);
      setIsSending(false);
      abortRef.current = null;
    } catch (err) {
      setIsSending(false);
      setProcessingStage("");
      setProcessingPercent(0);
      setRetrievalProgress({});
      abortRef.current = null;
      message.error(err instanceof Error ? err.message : "请求失败");
    }
  }

  function performanceNow(): number {
    const perf = globalThis.performance;
    return perf && typeof perf.now === "function" ? perf.now() : Date.now();
  }

  async function primeSourceInfo(sourceIds: string[]) {
    const missing = sourceIds.filter((id) => !sourceInfoMap[id]);
    if (!missing.length) return;
    try {
      const resp = await getSourceInfoBatch(missing);
      const next: Record<string, string> = {};
      for (const [k, v] of Object.entries(resp)) {
        next[k] = v?.file_name || k;
      }
      setSourceInfoMap((prev) => ({ ...prev, ...next }));
    } catch {
      // ignore
    }
  }

  async function openSource(sourceId: string) {
    setSourceDrawerOpen(true);
    setSourceDrawerTitle(sourceInfoMap[sourceId] || sourceId);
    setSourceDrawerLoading(true);
    try {
      const resp = await getSourceContent(sourceId);
      setSourceDrawerContent(resp.content || "");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "获取源内容失败");
      setSourceDrawerContent("");
    } finally {
      setSourceDrawerLoading(false);
    }
  }

  async function extractKgForMessage(m: ChatMessage) {
    try {
      const resp = await getKnowledgeGraphFromMessage({
        message: m.content,
        query: m.query,
      });
      setMessages((prev) =>
        prev.map((x) => (x.id === m.id ? { ...x, kgData: resp } : x)),
      );
      if (m.id === messages[messages.length - 1]?.id) setKgData(resp);
      setDebugTabKey("kg");
      message.success("已提取知识图谱");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "提取失败");
    }
  }

  async function submitFeedback(m: ChatMessage, isPositive: boolean) {
    if (!m.query) {
      message.warning("缺少 query，无法提交反馈");
      return;
    }
    if (feedbackPending[m.id]) return;
    try {
      setFeedbackPending((prev) => ({ ...prev, [m.id]: true }));
      const resp = await sendFeedback({
        message_id: m.id,
        query: m.query,
        is_positive: isPositive,
        thread_id: sessionId,
        request_id: m.requestId,
        agent_type: agentType,
      });
      const next = resp.feedback;
      if (next === "none") {
        setFeedbackState((prev) => {
          // remove key for "cancel"
          const copy = { ...prev };
          delete copy[m.id];
          return copy;
        });
      } else if (next === "positive" || next === "negative") {
        setFeedbackState((prev) => ({ ...prev, [m.id]: next }));
      } else {
        // Backward-compat: older backend versions don't return `feedback`.
        setFeedbackState((prev) => ({ ...prev, [m.id]: isPositive ? "positive" : "negative" }));
      }
      message.success(resp.action || "反馈已提交");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "提交反馈失败");
    } finally {
      setFeedbackPending((prev) => ({ ...prev, [m.id]: false }));
    }
  }

  function parseThinking(thinkingText: string): {
    queries: string[];
    kbSearches: string[];
    kbResults: string[];
    usefulInfo?: string;
    otherLines: string[];
  } {
    const lines = thinkingText
      .split(/\r?\n/g)
      .map((l) => l.trimEnd())
      .filter((l) => l.trim());

    const queries: string[] = [];
    const kbSearches: string[] = [];
    const kbResults: string[] = [];
    let usefulInfo: string | undefined;
    const otherLines: string[] = [];

    for (const line of lines) {
      if (line.includes("[深度研究] 执行查询:")) {
        queries.push(line.replace("[深度研究] 执行查询:", "").trim());
        continue;
      }
      if (line.includes("[KB检索] 开始搜索:")) {
        kbSearches.push(line.replace("[KB检索] 开始搜索:", "").trim());
        continue;
      }
      if (line.includes("[KB检索] 结果:")) {
        kbResults.push(line);
        continue;
      }
      if (line.includes("[深度研究] 发现有用信息:")) {
        usefulInfo = line.replace("[深度研究] 发现有用信息:", "").trim();
        continue;
      }
      otherLines.push(line);
    }

    return { queries, kbSearches, kbResults, usefulInfo, otherLines };
  }

  const perfStats = useMemo(() => {
    const groups = new Map<string, number[]>();
    for (const ev of perfEvents) {
      if (!groups.has(ev.op)) groups.set(ev.op, []);
      groups.get(ev.op)?.push(ev.ms);
    }
    const percentile = (arr: number[], p: number) => {
      if (!arr.length) return 0;
      const sorted = [...arr].sort((a, b) => a - b);
      const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * p));
      return sorted[idx] || 0;
    };
    return Array.from(groups.entries()).map(([op, arr]) => {
      const count = arr.length;
      const sum = arr.reduce((a, b) => a + b, 0);
      const avg = count ? sum / count : 0;
      const max = count ? Math.max(...arr) : 0;
      const p95 = percentile(arr, 0.95);
      return { key: op, op, count, avg, p95, max };
    });
  }, [perfEvents]);

  return (
    <Layout className="chat-container" style={{ height: "100vh", flexDirection: "column" }}>
      {/* Top Navigation Bar */}
      <div style={{
        height: 60,
        background: "#fff",
        borderBottom: "1px solid #f0f0f0",
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        flexShrink: 0,
        justifyContent: "space-between"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          <Typography.Text strong style={{ fontSize: 20 }}>Movie Agent</Typography.Text>
          <div style={{ display: "flex", gap: 8 }}>
            {[
              { key: "chat", label: "对话工作台", icon: <MessageOutlined /> },
              { key: "kg", label: "知识图谱", icon: <ProjectOutlined /> },
              { key: "sources", label: "源内容", icon: <FileTextOutlined /> },
              { key: "settings", label: "设置", icon: <SettingOutlined /> }
            ].map(item => (
              <div
                key={item.key}
                onClick={() => setActiveFeature(item.key as any)}
                style={{
                  padding: "8px 16px",
                  cursor: "pointer",
                  borderRadius: 6,
                  background: activeFeature === item.key ? "#e6f7ff" : "transparent",
                  color: activeFeature === item.key ? "#1890ff" : "inherit",
                  fontWeight: activeFeature === item.key ? 600 : 400,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  transition: "all 0.2s"
                }}
              >
                {item.icon}
                {item.label}
              </div>
            ))}
          </div>
        </div>
        <div /> {/* Placeholder for right side actions if needed */}
      </div>

      <Layout style={{ flex: 1, overflow: "hidden", flexDirection: "row" }}>

        {/* Left Sidebar - Only visible in Chat mode */}
        {activeFeature === "chat" && (
          <>
            <Layout.Sider
              width={sessionListWidth}
              theme="light"
              collapsible
              collapsed={!sessionListVisible}
              collapsedWidth={0}
              onCollapse={(collapsed) => setSessionListVisible(!collapsed)}
              trigger={null}
              className="layout-sider"
              style={{ borderRight: "1px solid #f0f0f0" }}
            >
              <SessionList
                userId={userId}
                currentSessionId={sessionId}
                onSelectSession={handleSelectSession}
                onNewSession={handleNewSession}
                style={{ height: "100%", width: "100%", borderRight: "none" }}
              />
            </Layout.Sider>

            {/* Resizer for Sidebar */}
            {sessionListVisible && (
              <div
                style={{
                  width: 4,
                  cursor: "col-resize",
                  background: isResizingRef.current === "left" ? "#1890ff" : "transparent",
                  zIndex: 100,
                  transition: "background 0.2s",
                }}
                onMouseDown={() => handleResizeStart("left")}
              />
            )}
          </>
        )}

        <Layout.Content className="chat-layout-content" style={{ display: activeFeature === "chat" ? "flex" : "none" }}>
          <div className="chat-header" style={{ flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button
                type="text"
                icon={sessionListVisible ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
                onClick={() => setSessionListVisible(!sessionListVisible)}
              />
              {/* <Typography.Text strong style={{ fontSize: 18, marginLeft: 4 }}>GraphRAG Chat</Typography.Text> */}
              {isIncognito && (
                <Tag color="#1f1f1f" style={{ display: "flex", alignItems: "center", gap: 4, borderRadius: 12, padding: "2px 10px", margin: 0 }}>
                  <span role="img" aria-label="incognito">🕶️</span>
                  无痕模式
                </Tag>
              )}
            </div>
            <Space>
              <Button
                size="small"
                icon={<VideoCameraOutlined />}
                onClick={() => setMemoryDrawerOpen(true)}
              >
                记忆中心
              </Button>
              <Button
                size="small"
                icon={<BugOutlined />}
                onClick={() => setDebugDrawerOpen(true)}
                disabled={!debugMode && !latestDebugData && !executionLogs.length && !rawThinking.trim()}
              >
                调试信息
              </Button>
              <Space align="center" size="small">
                <Switch
                  checked={debugMode}
                  onChange={(checked) => {
                    setDebugMode(checked);
                    // Debug mode requires streaming so we can fetch separated debug data
                    // via GET /api/v1/debug/{request_id} after the stream ends.
                    if (checked) setUseStream(true);
                  }}
                  size="small"
                />
                <Typography.Text style={{ fontSize: 12, color: debugMode ? "#1890ff" : "#999" }}>
                  调试
                </Typography.Text>
              </Space>
              <Button
                icon={<SettingOutlined />}
                onClick={() => setActiveFeature("settings")}
                type="text"
              >
                设置
              </Button>
            </Space>
          </div>


          <div className="message-list" ref={scrollRef}>
            <div className="message-list-content">
              {messages.length === 0 ? (
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  padding: "40px 24px"
                }}>
                  <Typography.Title level={3} style={{ marginBottom: 32, color: "#333" }}>
                    欢迎使用 Movie Agent
                  </Typography.Title>
                  <Space wrap style={{ justifyContent: "center", maxWidth: 700 }} size={[12, 12]}>
                    {exampleQuestions.map((q) => (
                      <div
                        key={q}
                        style={{
                          cursor: "pointer",
                          padding: "12px 20px",
                          fontSize: 15,
                          border: "1px solid #e0e0e0",
                          borderRadius: 8,
                          background: "#fff",
                          boxShadow: "0 2px 4px rgba(0,0,0,0.02)",
                          transition: "all 0.2s"
                        }}
                        onClick={() => setPromptValue(q)}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = "#1890ff";
                          e.currentTarget.style.color = "#1890ff";
                          e.currentTarget.style.transform = "translateY(-1px)";
                          e.currentTarget.style.boxShadow = "0 4px 12px rgba(24,144,255,0.15)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = "#e0e0e0";
                          e.currentTarget.style.color = "inherit";
                          e.currentTarget.style.transform = "none";
                          e.currentTarget.style.boxShadow = "0 2px 4px rgba(0,0,0,0.02)";
                        }}
                      >
                        {q}
                      </div>
                    ))}
                  </Space>
                </div>
              ) : (
                messages.map((m) => (
                  <div
                    id={`message-${m.id}`}
                    data-message-id={m.id}
                    className={`message-row ${m.role} ${highlightMessageId === m.id ? "highlight" : ""}`}
                    key={m.id}
                  >
                    {/* Avatar */}
                    <div className="message-avatar">
                      {m.role === "user" ? <UserOutlined /> : <RobotOutlined />}
                    </div>

                    {/* Content Container */}
                    <div className="message-content-container">
                      {/* Name & Time (Optional) */}
                      <div style={{ fontSize: 12, color: "#999", padding: "0 4px" }}>
                        {m.role === "user" ? "You" : "Movie Agent"}
                      </div>

                      {/* Bubble */}
                      <div className={`message-bubble ${m.role}`}>
                        {m.role === "assistant" && agentType === "deep_research_agent" && (showThinking || debugMode) && m.rawThinking?.trim() ? (
                          <div className="thinking-wrapper">
                            <Collapse
                              size="small"
                              ghost
                              items={[
                                {
                                  key: "thinking",
                                  label: (
                                    <Space size="small">
                                      <span role="img" aria-label="thinking" style={{ fontSize: "1.2em" }}>🧠</span>
                                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                                        Thinking Process
                                      </Typography.Text>
                                    </Space>
                                  ),
                                  children: (
                                    <div className="thinking-content">
                                      {m.rawThinking}
                                    </div>
                                  ),
                                },
                              ]}
                            />
                          </div>
                        ) : null}

                        {m.role === "assistant" ? (
                          <div
                            className={`message-markdown ${isSending && m.id === messages[messages.length - 1].id ? "streaming" : ""
                              }`}
                          >
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code(props) {
                                  const { children, className, node, ...rest } = props;
                                  const match = /language-(\w+)/.exec(className || "");
                                  return match ? (
                                    <CodeBlock className={className} {...rest}>
                                      {children}
                                    </CodeBlock>
                                  ) : (
                                    <code className={className} {...rest}>
                                      {children}
                                    </code>
                                  );
                                },
                              }}
                            >
                              {m.content || (isSending ? "…" : "")}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          m.content
                        )}

                        {/* Sources (Assistant only) */}
                        {m.role === "assistant" && m.sourceIds?.length ? (
                          <div className="message-sources" style={{ marginTop: 8 }}>
                            <Space wrap size={[0, 4]}>
                              {m.sourceIds.slice(0, 10).map((id) => (
                                <Tag
                                  key={id}
                                  className="source-tag"
                                  onClick={() => openSource(id)}
                                >
                                  {sourceInfoMap[id] || id}
                                </Tag>
                              ))}
                              {m.sourceIds.length > 10 ? (
                                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                  +{m.sourceIds.length - 10} more
                                </Typography.Text>
                              ) : null}
                            </Space>
                          </div>
                        ) : null}
                      </div>

                      {/* Action Bar (Assistant Only) */}
                      {m.role === "assistant" && (
                        <div className="message-actions-bar">
                          <Dropdown
                            menu={{
                              items: [
                                {
                                  key: 'copy-text',
                                  label: '复制',
                                  onClick: () => {
                                    navigator.clipboard.writeText(m.content);
                                    message.success("已复制");
                                  },
                                },
                                {
                                  key: 'copy-markdown',
                                  label: '复制为Markdown',
                                  onClick: () => {
                                    navigator.clipboard.writeText(m.content);
                                    message.success("已复制为Markdown");
                                  },
                                },
                              ],
                            }}
                            trigger={['click']}
                          >
                            <Button
                              type="text"
                              size="small"
                              icon={<CopyOutlined />}
                              onClick={() => {
                                navigator.clipboard.writeText(m.content);
                                message.success("已复制");
                              }}
                              className="action-icon-btn"
                            />
                          </Dropdown>
                          <Button
                            type="text"
                            size="small"
                            icon={<LikeOutlined style={{ color: feedbackState[m.id] === "positive" ? "#52c41a" : undefined }} />}
                            onClick={() => submitFeedback(m, true)}
                            className="action-icon-btn"
                          />
                          <Button
                            type="text"
                            size="small"
                            icon={<DislikeOutlined style={{ color: feedbackState[m.id] === "negative" ? "#ff4d4f" : undefined }} />}
                            onClick={() => submitFeedback(m, false)}
                            className="action-icon-btn"
                          />
                          <Button
                            type="text"
                            size="small"
                            onClick={() => extractKgForMessage(m)}
                            className="action-icon-btn"
                            style={{ fontSize: 12 }}
                          >
                            Graph
                          </Button>
                          {/* Regenerate button - only for the last assistant message */}
                          {messages[messages.length - 1].id === m.id && (
                            <Button
                              type="text"
                              size="small"
                              icon={<ReloadOutlined />}
                              onClick={handleRegenerate}
                              className="action-icon-btn"
                              disabled={isSending}
                            />
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>



          {/* Composer Area */}
          <div className="chat-footer">
            <div className="composer-content">
              {isSending && processingStage && (
                <div className="streaming-status-bar">
                  <Space>
                    <Progress
                      type="circle"
                      percent={processingPercent || 5}
                      size={14}
                      strokeWidth={12}
                      strokeColor="var(--primary-color)"
                      trailColor="rgba(0,0,0,0.05)"
                    />
                    <Typography.Text style={{ fontSize: 13, fontWeight: 500, color: "var(--text-secondary)" }}>
                      {processingStage}
                    </Typography.Text>
                  </Space>

                  {retrievalEntries.length > 0 && (
                    <Space size={4}>
                      {retrievalEntries.map(([agent, info]) => (
                        <Tag
                          key={agent}
                          bordered={false}
                          style={{
                            borderRadius: 12,
                            fontSize: 11,
                            margin: 0,
                            background: info.error ? "#fff1f0" : "rgba(0,0,0,0.04)",
                            color: info.error ? "#ff4d4f" : "var(--text-tertiary)"
                          }}
                        >
                          {agent}
                          {typeof info.retrievalCount === "number" ? ` ${info.retrievalCount}` : ""}
                        </Tag>
                      ))}
                    </Space>
                  )}
                </div>
              )}
              <div className="composer-wrapper">
                <div className="prompt-hints">
                  {[
                    { label: "总结摘要", value: "请总结以上内容的要点" },
                    { label: "解释代码", value: "请解释这段代码的逻辑" },
                    { label: "推荐电影", value: "推荐几部类似星际穿越的科幻电影" },
                    { label: "/clear", value: "/clear", isCommand: true },
                  ].map((hint) => (
                    <Tag
                      key={hint.label}
                      className="prompt-hint-tag"
                      onClick={() => {
                        if (hint.isCommand && hint.value === "/clear") {
                          handleClear(true);
                          return;
                        }
                        setPromptValue(hint.value);
                      }}
                    >
                      {hint.label}
                    </Tag>
                  ))}
                </div>
                <div className="composer-input-wrapper">
                  <Input.TextArea
                    value={promptValue}
                    onChange={(e) => {
                      const val = e.target.value;
                      setPromptValue(val);
                      // Simple Slash Command Check
                      if (val === "/clear") {
                        // Can show a hint or wait for enter
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        if (promptValue.trim() === "/clear") {
                          handleClear(true);
                          setPromptValue("");
                          return;
                        }
                        handleSend();
                      }
                    }}
                    autoSize={{ minRows: 3, maxRows: 8 }}
                    placeholder="Message GraphRAG... (Try /clear or @agent)"
                    disabled={isSending}
                    className="composer-textarea"
                  />
                  {promptValue.endsWith("@") && (
                    <div className="agent-selector-popover" style={{
                      position: "absolute",
                      bottom: "100%",
                      left: 20,
                      marginBottom: 8,
                      background: "#fff",
                      borderRadius: 8,
                      boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                      padding: 8,
                      zIndex: 1000,
                      border: "1px solid #eee",
                      minWidth: 150
                    }}>
                      <div style={{ fontSize: 12, color: "#999", marginBottom: 4, padding: "0 4px" }}>Select Agent</div>
                      {agentOptions.map(opt => (
                        <div
                          key={opt.value}
                          style={{
                            padding: "6px 12px",
                            cursor: "pointer",
                            borderRadius: 4,
                            background: agentType === opt.value ? "#e6f7ff" : "transparent",
                            color: agentType === opt.value ? "#1890ff" : "#333",
                            fontSize: 13
                          }}
                          className="agent-option-item"
                          onClick={() => {
                            setAgentType(opt.value);
                            setPromptValue(prev => prev.slice(0, -1)); // Remove the '@'
                            message.success(`Switched to ${opt.label}`);
                          }}
                        >
                          {opt.label}
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="composer-send-btn-wrapper">
                    {isSending ? (
                      <Button
                        shape="circle"
                        icon={<div style={{ width: 8, height: 8, background: "currentColor", borderRadius: 1 }} />}
                        onClick={handleStop}
                        className="stop-btn"
                      />
                    ) : (
                      <Button
                        type="primary"
                        shape="circle"
                        icon={<ArrowUpOutlined />}
                        onClick={handleSend}
                        disabled={!promptValue.trim()}
                        className="send-btn"
                      />
                    )}
                  </div>
                </div>

                <div className="composer-footer">
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      Enter 发送，Shift+Enter 换行 {canStream ? "| 流式开启" : ""}
                    </Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 12, opacity: 0.6 }}>
                      AI 生成内容可能不准确，请核实重要信息。
                    </Typography.Text>
                  </div>
                </div>
              </div>
            </div>
          </div>


        </Layout.Content>

        {/* Settings View (formerly Right Sidebar) */}
        <Layout.Content
          className="settings-view"
          style={{
            display: activeFeature === "settings" ? "block" : "none",
            padding: 24,
            overflowY: "auto",
            background: "#fdfdfd",
            flex: 1
          }}
        >
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <Card title="控制台" size="small">
              <Row gutter={[12, 12]}>
                <Col span={24}>
                  <Typography.Text strong>Agent</Typography.Text>
                  <Radio.Group
                    style={{ display: "block", marginTop: 8 }}
                    optionType="button"
                    buttonStyle="solid"
                    options={agentOptions}
                    value={agentType}
                    onChange={(e) => setAgentType(e.target.value)}
                  />
                </Col>

                <Col span={24}>
                  <Divider style={{ margin: "12px 0" }} orientation="left" plain>隐私与记忆</Divider>
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span>无痕模式 (Incognito)</span>
                      <Switch
                        checked={isIncognito}
                        onChange={(checked) => {
                          setIsIncognito(checked);
                          localStorage.setItem("graphrag.privacy.incognito", String(checked));
                          message.info(checked ? "已开启无痕模式，新的对话将不会被记忆" : "已关闭无痕模式");
                        }}
                      />
                    </div>
                    <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: -8 }}>
                      开启后，AI 不会生成摘要、不会通过情节记忆学习您的偏好，也不会自动捕获待看清单。
                    </Typography.Text>

                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                      <span>自动捕获待看清单 (Auto-Capture)</span>
                      <Switch
                        checked={autoCaptureEnabled}
                        onChange={(checked) => {
                          setAutoCaptureEnabled(checked);
                          localStorage.setItem("graphrag.privacy.autoCapture", String(checked));
                        }}
                        disabled={isIncognito} // Incognito implicitly disables memory write
                      />
                    </div>
                    <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: -8 }}>
                      允许 AI 从对话中自动识别并添加电影到您的 Watchlist。
                    </Typography.Text>
                  </Space>
                </Col>

                <Col span={24}>
                  <Divider style={{ margin: "12px 0" }} orientation="left" plain>调试选项</Divider>
                  <Space direction="vertical">
                    <Checkbox
                      checked={debugMode}
                      onChange={(e) => {
                        setDebugMode(e.target.checked);
                        if (e.target.checked) setUseStream(true);
                      }}
                    >
                      调试模式（流式输出 + 调试数据另取）
                    </Checkbox>
                    <Checkbox
                      checked={useStream}
                      onChange={(e) => setUseStream(e.target.checked)}
                      disabled={debugMode}
                    >
                      使用流式输出（SSE）（调试模式下强制开启）
                    </Checkbox>
                  </Space>
                </Col>

                {agentType === "deep_research_agent" && (
                  <Col span={24}>
                    <Divider style={{ margin: "12px 0" }} />
                    <Space direction="vertical">
                      <Checkbox
                        checked={useDeeperTool}
                        onChange={(e) => setUseDeeperTool(e.target.checked)}
                      >
                        使用增强版研究工具
                      </Checkbox>
                      <Checkbox
                        checked={showThinking}
                        onChange={(e) => setShowThinking(e.target.checked)}
                      >
                        显示推理过程
                      </Checkbox>
                    </Space>
                  </Col>
                )}

                {agentType === "fusion_agent" && (
                  <Col span={24}>
                    <Divider style={{ margin: "12px 0" }} />
                    <Checkbox
                      checked={useChainExploration}
                      onChange={(e) => setUseChainExploration(e.target.checked)}
                    >
                      使用链式探索（fusion）
                    </Checkbox>
                  </Col>
                )}
              </Row>
            </Card>



            <Card title="调试信息" size="small" style={{ marginTop: 12 }}>
              <Tabs
                activeKey={debugTabKey}
                onChange={setDebugTabKey}
                items={[
                  {
                    key: "thinking",
                    label: `推理过程 (${rawThinking ? rawThinking.split(/\r?\n/).filter((l) => l.trim()).length : 0})`,
                    children: (() => {
                      if (!rawThinking.trim()) {
                        return (
                          <Typography.Text type="secondary">
                            暂无推理过程（仅 deep_research_agent 且开启“显示推理过程”/调试模式时有）
                          </Typography.Text>
                        );
                      }
                      const parsed = parseThinking(rawThinking);
                      const toolType = useDeeperTool ? "增强版(DeeperResearch)" : "标准版(DeepResearch)";
                      return (
                        <Space direction="vertical" style={{ width: "100%" }} size="middle">
                          <Typography.Text type="secondary">当前工具：{toolType}</Typography.Text>

                          {parsed.queries.length ? (
                            <div>
                              <Typography.Text strong>执行的查询</Typography.Text>
                              <div style={{ marginTop: 8 }}>
                                <Space direction="vertical" style={{ width: "100%" }} size={6}>
                                  {parsed.queries.slice(0, 20).map((q, idx) => (
                                    <div key={`${q}-${idx}`} style={{ background: "#f5f5f5", padding: "6px 10px", borderRadius: 6 }}>
                                      {q}
                                    </div>
                                  ))}
                                  {parsed.queries.length > 20 ? (
                                    <Typography.Text type="secondary">
                                      …（共 {parsed.queries.length} 条）
                                    </Typography.Text>
                                  ) : null}
                                </Space>
                              </div>
                            </div>
                          ) : null}

                          {parsed.usefulInfo ? (
                            <div>
                              <Typography.Text strong>发现的有用信息</Typography.Text>
                              <div style={{ marginTop: 8, background: "#E8F5E9", padding: "8px 10px", borderRadius: 6 }}>
                                {parsed.usefulInfo}
                              </div>
                            </div>
                          ) : null}

                          {parsed.kbSearches.length || parsed.kbResults.length ? (
                            <div>
                              <Typography.Text strong>知识库检索</Typography.Text>
                              <div style={{ marginTop: 8 }}>
                                {parsed.kbSearches.length ? (
                                  <div style={{ marginBottom: 10 }}>
                                    <Typography.Text type="secondary">搜索内容</Typography.Text>
                                    <div style={{ marginTop: 6 }}>
                                      <Space direction="vertical" style={{ width: "100%" }} size={6}>
                                        {parsed.kbSearches.slice(0, 20).map((s, idx) => (
                                          <div key={`${s}-${idx}`} style={{ background: "#FFF8E1", padding: "6px 10px", borderRadius: 6 }}>
                                            {s}
                                          </div>
                                        ))}
                                      </Space>
                                    </div>
                                  </div>
                                ) : null}
                                {parsed.kbResults.length ? (
                                  <div>
                                    <Typography.Text type="secondary">检索结果</Typography.Text>
                                    <pre style={{ whiteSpace: "pre-wrap", margin: "6px 0 0 0" }}>
                                      {parsed.kbResults.join("\n")}
                                    </pre>
                                  </div>
                                ) : null}
                              </div>
                            </div>
                          ) : null}

                          <Collapse
                            size="small"
                            items={[
                              {
                                key: "raw",
                                label: "原始推理日志",
                                children: (
                                  <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                                    {rawThinking}
                                  </pre>
                                ),
                              },
                            ]}
                          />
                        </Space>
                      );
                    })(),
                  },
                  {
                    key: "logs",
                    label: `执行轨迹 (${executionLogs.length})`,
                    children: (
                      <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                        {executionLogs.length
                          ? JSON.stringify(executionLogs, null, 2)
                          : "暂无执行轨迹（需开启调试模式或后端返回）"}
                      </pre>
                    ),
                  },
                  {
                    key: "iterations",
                    label: `迭代信息 (${iterations.length})`,
                    children: (
                      <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                        {iterations.length
                          ? JSON.stringify(iterations, null, 2)
                          : "暂无迭代信息"}
                      </pre>
                    ),
                  },
                  {
                    key: "kg",
                    label: `知识图谱 (${kgData?.nodes?.length ?? 0})`,
                    children: (
                      <KnowledgeGraphPanel
                        nodes={kgData?.nodes ?? []}
                        links={kgData?.links ?? []}
                        raw={kgData}
                        height={360}
                      />
                    ),
                  },
                  {
                    key: "reference",
                    label: "reference",
                    children: (
                      <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                        {reference ? JSON.stringify(reference, null, 2) : "暂无 reference"}
                      </pre>
                    ),
                  },
                  {
                    key: "perf",
                    label: `性能 (${perfEvents.length})`,
                    children: (
                      <Space direction="vertical" style={{ width: "100%" }}>
                        <Button size="small" onClick={() => setPerfEvents([])} disabled={!perfEvents.length}>
                          清除性能数据
                        </Button>
                        <Table
                          size="small"
                          rowKey="key"
                          dataSource={perfStats}
                          pagination={false}
                          columns={[
                            { title: "op", dataIndex: "op" },
                            { title: "count", dataIndex: "count", width: 90 },
                            {
                              title: "avg(ms)",
                              dataIndex: "avg",
                              width: 110,
                              render: (v: unknown) => Number(v).toFixed(1),
                            },
                            {
                              title: "p95(ms)",
                              dataIndex: "p95",
                              width: 110,
                              render: (v: unknown) => Number(v).toFixed(1),
                            },
                            {
                              title: "max(ms)",
                              dataIndex: "max",
                              width: 110,
                              render: (v: unknown) => Number(v).toFixed(1),
                            },
                          ]}
                        />
                        <Collapse
                          size="small"
                          items={[
                            {
                              key: "raw",
                              label: "原始事件",
                              children: (
                                <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                                  {perfEvents.length ? JSON.stringify(perfEvents, null, 2) : "暂无数据"}
                                </pre>
                              ),
                            },
                          ]}
                        />
                      </Space>
                    ),
                  },
                ]}
              />
            </Card>
          </div>
        </Layout.Content>

        {/* Knowledge Graph View */}
        <div style={{ display: activeFeature === "kg" ? "flex" : "none", flex: 1, flexDirection: "column", padding: 24, overflow: "hidden" }}>
          <KnowledgeGraphPanel
            nodes={kgData?.nodes ?? []}
            links={kgData?.links ?? []}
            raw={kgData}
            height={800}
          />
        </div>

        {/* Sources View */}
        <div style={{ display: activeFeature === "sources" ? "block" : "none", flex: 1, padding: 24, overflowY: "auto" }}>
          <Typography.Title level={4}>Source Content</Typography.Title>
          {reference ? (
            <pre>{JSON.stringify(reference, null, 2)}</pre>
          ) : (
            <Typography.Text type="secondary">No sources loaded.</Typography.Text>
          )}
        </div>


        <Drawer
          title={sourceDrawerTitle}
          open={sourceDrawerOpen}
          width={760}
          onClose={() => setSourceDrawerOpen(false)}
        >
          {sourceDrawerLoading ? (
            <Typography.Text>加载中...</Typography.Text>
          ) : (
            <pre style={{ whiteSpace: "pre-wrap" }}>{sourceDrawerContent}</pre>
          )}
        </Drawer>

        <DebugDrawer
          open={debugDrawerOpen}
          onClose={() => setDebugDrawerOpen(false)}
          debugData={latestDebugData}
          debugMode={debugMode}
          onOpenSource={async (sourceId) => {
            setSourceDrawerLoading(true);
            setSourceDrawerOpen(true);
            setSourceDrawerTitle(sourceId);
            try {
              const resp = await getSourceContent(sourceId);
              setSourceDrawerContent(resp.content || "");
            } catch (err) {
              console.error("Failed to fetch source:", err);
              setSourceDrawerContent("");
            } finally {
              setSourceDrawerLoading(false);
            }
          }}
        />

        <MemoryDrawer
          open={memoryDrawerOpen}
          onClose={() => setMemoryDrawerOpen(false)}
          userId={userId}
          sessionId={sessionId}
          onJumpToMessage={(messageId) => {
            void jumpToMessage(messageId);
          }}
        />

      </Layout>
    </Layout >
  );
}
