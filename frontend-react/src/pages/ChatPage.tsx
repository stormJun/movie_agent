import { useEffect, useMemo, useRef, useState } from "react";
import { MenuFoldOutlined, MenuUnfoldOutlined, ArrowUpOutlined, SettingOutlined, BugOutlined, MessageOutlined, ProjectOutlined, FileTextOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  Divider,
  Drawer,
  Flex,
  Input,
  Layout,
  Progress,
  Radio,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentType, StreamEvent } from "../types/chat";
import { chat, chatStream, clearChat, getMessages, type MessageItem } from "../services/chat";
import { getKnowledgeGraphFromMessage } from "../services/graph";
import type { KnowledgeGraphResponse } from "../types/graph";
import { getSourceContent, getSourceInfoBatch } from "../services/source";
import { sendFeedback } from "../services/feedback";

import { getExampleQuestions } from "../services/chat";
import { KnowledgeGraphPanel } from "../components/KnowledgeGraphPanel";
import { SessionList } from "../components/SessionList";

type Role = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  query?: string;
  sourceIds?: string[];
  kgData?: KnowledgeGraphResponse;
  reference?: unknown;
  rawThinking?: string;
};

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
  const [debugMode, setDebugMode] = useState<boolean>(false);
  const [useStream, setUseStream] = useState<boolean>(true);
  const [useDeeperTool, setUseDeeperTool] = useState<boolean>(true);
  const [showThinking, setShowThinking] = useState<boolean>(false);
  const [useChainExploration, setUseChainExploration] = useState<boolean>(true);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [executionLogs, setExecutionLogs] = useState<unknown[]>([]);
  const [iterations, setIterations] = useState<unknown[]>([]);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [processingStage, setProcessingStage] = useState<string>("");
  const [processingPercent, setProcessingPercent] = useState<number>(0);
  const [exampleQuestions, setExampleQuestions] = useState<string[]>([]);

  // Fallback examples in case backend is empty
  const DEFAULT_EXAMPLES = [
    "推荐几部90年代的高分科幻电影",
    "Inception的导演是谁？",
    "黑客帝国的主要类型是什么？",
    "找几部类似星际穿越的电影"
  ];

  useEffect(() => {
    console.log("Loading examples...");
    getExampleQuestions()
      .then((qs) => {
        console.log("Loaded examples:", qs);
        if (qs && qs.length > 0) {
          setExampleQuestions(qs);
        } else {
          setExampleQuestions(DEFAULT_EXAMPLES);
        }
      })
      .catch((e) => {
        console.warn("Failed to load examples", e);
        setExampleQuestions(DEFAULT_EXAMPLES);
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

  const canStream = useMemo(() => useStream && !debugMode, [useStream, debugMode]);
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
      debug: debugMode,
      agent_type: agentType,
      use_deeper_tool: agentType === "deep_research_agent" ? useDeeperTool : undefined,
      show_thinking: agentType === "deep_research_agent" ? showThinking : undefined,
      use_chain_exploration: agentType === "fusion_agent" ? useChainExploration : undefined,
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
        if (ev.status === "done") {
          setProcessingStage("完成");
          setProcessingPercent(100);
          const doneThinking =
            typeof (ev as { thinking_content?: unknown }).thinking_content === "string"
              ? String((ev as { thinking_content?: string }).thinking_content)
              : "";
          if (doneThinking.trim()) {
            setRawThinking(doneThinking);
            updateAssistantThinking(doneThinking);
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
    if (feedbackState[m.id]) return;
    try {
      setFeedbackPending((prev) => ({ ...prev, [m.id]: true }));
      const resp = await sendFeedback({
        message_id: m.id,
        query: m.query,
        is_positive: isPositive,
        thread_id: sessionId,
        agent_type: agentType,
      });
      setFeedbackState((prev) => ({ ...prev, [m.id]: isPositive ? "positive" : "negative" }));
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
            </div>
            <Space>
              <Button
                icon={<BugOutlined />}
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
                  <div className={`message ${m.role}`} key={m.id}>
                    <div className="meta">
                      {m.role === "user" ? "User" : "Assistant"} ·{" "}
                      {new Date(m.createdAt).toLocaleTimeString()}
                    </div>
                    <div className="bubble">
                      {m.role === "assistant" ? (
                        <Space direction="vertical" style={{ width: "100%" }} size="small">
                          {agentType === "deep_research_agent" && (showThinking || debugMode) ? (
                            m.rawThinking?.trim() ? (
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
                            ) : null
                          ) : null}

                          <div className="message-markdown">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {m.content || (isSending ? "…" : "")}
                            </ReactMarkdown>
                          </div>

                          <div className="message-actions">
                            <Space wrap size="small">
                              <Button
                                type="text"
                                size="small"
                                onClick={() => submitFeedback(m, true)}
                                disabled={!!feedbackState[m.id] || !!feedbackPending[m.id]}
                                loading={!!feedbackPending[m.id]}
                                className="action-icon-btn"
                              >
                                👍
                              </Button>
                              <Button
                                type="text"
                                size="small"
                                onClick={() => submitFeedback(m, false)}
                                disabled={!!feedbackState[m.id] || !!feedbackPending[m.id]}
                                loading={!!feedbackPending[m.id]}
                                className="action-icon-btn"
                              >
                                👎
                              </Button>
                              <Button
                                type="text"
                                size="small"
                                onClick={() => extractKgForMessage(m)}
                                className="action-text-btn"
                              >
                                Extract Graph
                              </Button>
                              {feedbackState[m.id] ? (
                                <Tag color={feedbackState[m.id] === "positive" ? "green" : "red"} style={{ margin: 0 }}>
                                  {feedbackState[m.id] === "positive" ? "Liked" : "Disliked"}
                                </Tag>
                              ) : null}
                            </Space>

                            {m.sourceIds?.length ? (
                              <div className="message-sources">
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
                        </Space>
                      ) : (
                        <Typography.Paragraph style={{ marginBottom: 0 }}>
                          {m.content}
                        </Typography.Paragraph>
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
                <Alert
                  message={
                    <Space>
                      <Progress
                        type="circle"
                        percent={processingPercent || 5}
                        size={20}
                        style={{ marginRight: 8 }}
                      />
                      <Typography.Text type="secondary">{processingStage}</Typography.Text>
                    </Space>
                  }
                  description={
                    retrievalEntries.length ? (
                      <Space wrap>
                        {retrievalEntries.map(([agent, info]) => (
                          <Tag key={agent} color={info.error ? "red" : "blue"}>
                            {agent}
                            {typeof info.retrievalCount === "number"
                              ? `：命中 ${info.retrievalCount}`
                              : ""}
                            {info.error ? "（异常）" : ""}
                          </Tag>
                        ))}
                      </Space>
                    ) : null
                  }
                  type="info"
                  style={{ marginBottom: 12 }}
                />
              )}
              <div className="composer-wrapper">
                <div className="composer-input-wrapper">
                  <Input.TextArea
                    value={promptValue}
                    onChange={(e) => setPromptValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    autoSize={{ minRows: 3, maxRows: 8 }}
                    placeholder="Message GraphRAG..."
                    disabled={isSending}
                    className="composer-textarea"
                  />
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
                  <Typography.Text type="secondary">
                    Enter 发送，Shift+Enter 换行 {canStream ? "| 流式开启" : ""}
                  </Typography.Text>
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
                  <Divider style={{ margin: "12px 0" }} />
                  <Space direction="vertical">
                    <Checkbox
                      checked={debugMode}
                      onChange={(e) => {
                        setDebugMode(e.target.checked);
                        if (e.target.checked) setUseStream(false);
                      }}
                    >
                      调试模式（关闭流式）
                    </Checkbox>
                    <Checkbox
                      checked={useStream}
                      onChange={(e) => setUseStream(e.target.checked)}
                      disabled={debugMode}
                    >
                      使用流式输出（SSE）
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

      </Layout>
    </Layout>
  );
}
