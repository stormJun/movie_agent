import { mpApi } from '../../utils/config';
import { mpPostSse, MpStreamFrame } from '../../utils/mpStreamClient';
import { fetchMoviesBulk, MovieCard, postFeedback } from '../../utils/api';
import { randomId } from '../../utils/id';

type Msg = {
  role: 'user' | 'assistant';
  text: string;
  suggestions?: string[];
  timestamp?: number;
  id?: string;
  timeStr?: string;
  showTime?: boolean;
  movie_cards?: MovieCard[];
  movie_cards_title?: string;
  // Backend message metadata (used for feedback).
  message_id?: string;
  thread_id?: string;
  request_id?: string;
  query?: string;
  agent_type?: string;
  feedback?: 'positive' | 'negative' | 'none';
};

const DEFAULT_INPUT_HEIGHT = 40; // Default textarea height in rpx (tight fit for text)
const MAX_INPUT_LINE_COUNT = 7; // Maximum lines before scrolling

Page({
  data: {
    messages: [] as Msg[],
    inputText: '',
    sending: false,
    loading: false,
    loadingTip: '',
    showTyping: false,
    scrollTop: 0,
    scrollIntoView: '',
    navBarHeight: 0,
    inputBarHeight: 116, // Base composer height (including padding + textarea + safe-area)
    inputHeight: DEFAULT_INPUT_HEIGHT, // Textarea height in rpx
    inputLineCount: 1, // Current line count
    maxInputLineCount: MAX_INPUT_LINE_COUNT, // Max lines before auto-height disables
    showScrollToBottom: false,
    keyboardHeight: 0,
  },

  onLoad() {
    const userId = wx.getStorageSync('mp_user_id') || randomId('u');
    wx.setStorageSync('mp_user_id', userId);
    const sessionId = wx.getStorageSync('mp_session_id') || randomId('s');
    wx.setStorageSync('mp_session_id', sessionId);

    // Calculate navbar height (navigation bar height + status bar height)
    // NOTE: wx.getSystemInfoSync is deprecated in newer SDKs; use getWindowInfo instead.
    const windowInfo = (wx as any).getWindowInfo?.();
    const statusBarHeight = (windowInfo && windowInfo.statusBarHeight) || 20;
    const navBarHeight = statusBarHeight + 44; // 44 is standard nav bar height

    this.setData({
      navBarHeight,
    });

    // Listen to keyboard height changes
    wx.onKeyboardHeightChange((res: any) => {
      const { height } = res;
      this.setData({ keyboardHeight: height });
    });
  },

  noop() { },

  onNewSession() {
    const hasMessages = Array.isArray(this.data.messages) && this.data.messages.length > 0;
    const isBusy = Boolean(this.data.sending || this.data.loading);

    const doReset = () => {
      try {
        const task = (this as any)._activeTask;
        if (task && typeof task.abort === 'function') {
          task.abort();
        }
      } catch (_e) { }

      const newSessionId = randomId('s');
      wx.setStorageSync('mp_session_id', newSessionId);
      (this as any)._activeTask = null;
      (this as any)._pendingMovieCards = undefined;
      (this as any)._pendingMovieCardsTitle = undefined;
      (this as any)._feedbackPending = {};

      this.setData({
        messages: [],
        inputText: '',
        sending: false,
        loading: false,
        loadingTip: '',
        showTyping: false,
        scrollTop: 0,
        scrollIntoView: '',
        showScrollToBottom: false,
        inputHeight: DEFAULT_INPUT_HEIGHT,
        inputLineCount: 1,
      });
    };

    if (!hasMessages && !isBusy) {
      doReset();
      return;
    }

    wx.showModal({
      title: '新会话',
      content: isBusy
        ? '当前正在生成回答，开启新会话会停止本次生成并清空对话。是否继续？'
        : '开启新会话会清空当前对话。是否继续？',
      confirmText: '继续',
      cancelText: '取消',
      success: (res: any) => {
        if (res?.confirm) {
          doReset();
        }
      },
    });
  },

  onScroll(e: any) {
    // Show/hide scroll-to-bottom button based on scroll position
    const scrollTop = e.detail.scrollTop;
    const scrollHeight = e.detail.scrollHeight;
    const viewHeight = e.detail.height;

    // Show button if not at bottom (with 100px threshold)
    const isAtBottom = scrollHeight - scrollTop - viewHeight < 100;
    this.setData({
      showScrollToBottom: !isAtBottom,
    });
  },

  onScrollToBottom() {
    this._scrollToBottom();
  },

  onInputFocus(e: any) {
    // Keyboard height is available in e.detail.height
    const keyboardHeight = e.detail.height || 0;
    this.setData({ keyboardHeight });
    this._scrollToBottom();
  },

  onInputBlur(e: any) {
    this.setData({ keyboardHeight: 0 });
  },

  onLineChange(e: any) {
    // Handle textarea height changes matching reference implementation
    const detail = e.detail || {};
    const lineCount = detail.lineCount || 1;
    let heightRpx = detail.heightRpx || 0;

    // Convert px to rpx if needed
    if ((!heightRpx || heightRpx <= 0) && typeof detail.height === 'number' && detail.height > 0) {
      // Assume 2px = 1rpx conversion (WeChat miniprogram standard)
      heightRpx = detail.height * 2;
    }

    const oldHeight = this.data.inputHeight;
    const oldLineCount = this.data.inputLineCount;
    const maxLineCount = this.data.maxInputLineCount;

    // Calculate safe height (minimum 38rpx)
    const safeHeight = Math.max(DEFAULT_INPUT_HEIGHT, Math.round(heightRpx));
    let newHeight = safeHeight;

    // Cap height at max line count
    if (lineCount > maxLineCount && safeHeight > 0) {
      const perLine = safeHeight / lineCount;
      newHeight = Math.max(DEFAULT_INPUT_HEIGHT, Math.round(perLine * maxLineCount));
    }

    // Update if changed
    if (oldHeight !== newHeight || oldLineCount !== lineCount) {
      this.setData({
        inputLineCount: lineCount,
        inputHeight: newHeight,
      });
    }
  },

  onInput(e: any) {
    this.setData({ inputText: e.detail.value });
  },

  onTapSuggestion(e: any) {
    const text = e.currentTarget?.dataset?.text || '';
    if (!text) return;

    // Prevent concurrent requests
    if (this.data.sending || this.data.loading) {
      return;
    }

    // Set the input text and auto-send
    this.setData({ inputText: text });
    this.onSend();
  },

  onClear() {
    this.setData({
      inputText: '',
      inputHeight: DEFAULT_INPUT_HEIGHT,
      inputLineCount: 1,
    });
  },

  async onSend() {
    if (this.data.sending || this.data.loading) {
      return;
    }
    const text = (this.data.inputText || '').trim();
    if (!text) {
      return;
    }

    const userId = wx.getStorageSync('mp_user_id') || 'u1';
    const sessionId = wx.getStorageSync('mp_session_id') || randomId('s');
    wx.setStorageSync('mp_session_id', sessionId);

    const now = Date.now();
    const prevMsg = this.data.messages[this.data.messages.length - 1];
    const timeDiff = prevMsg ? now - (prevMsg.timestamp || 0) : Infinity;
    const showTime = timeDiff > 5 * 60 * 1000; // Show time if more than 5 minutes apart

    const userMsg: Msg = {
      role: 'user',
      text,
      timestamp: now,
      id: `msg-${now}`,
      timeStr: this._formatTime(now),
      showTime,
      // Ensure component props stay strongly typed (avoid "expected String but got null").
      message_id: '',
      thread_id: '',
      request_id: '',
      agent_type: '',
      query: '',
      feedback: 'none',
    };

    const messages = [...this.data.messages, userMsg];
    this.setData({
      messages,
      inputText: '',
      sending: true,
      loading: true,
      loadingTip: '正在理解问题…',
      showTyping: true,
      inputHeight: DEFAULT_INPUT_HEIGHT,
      inputLineCount: 1,
    });
    this._scrollToBottom();

    let assistantIdx = messages.length;
    let acc = '';
    const userQuery = text;

    const task = mpPostSse(
      mpApi('/api/v1/mp/chat/stream'),
      {
        message: text,
        user_id: userId,
        session_id: sessionId,
        kb_prefix: 'movie',
        debug: true,
        incognito: false,
        watchlist_auto_capture: true,
      },
      {
        onFrame: async (frame: MpStreamFrame) => {
          this._handleFrame(frame, assistantIdx, acc);
          if (frame.type === 'status') {
            // Only show progress tips while we're still in the "pre-token" phase.
            if (this.data.showTyping) {
              const tip = this._formatProgressTip(frame?.content);
              if (tip) {
                this.setData({ loadingTip: tip });
              }
            }
          } else if (frame.type === 'chunk' && typeof frame.content === 'string') {
            // Hide the typing indicator as soon as we receive the first token
            // (otherwise we show two "assistant avatars": one for typing, one for text).
            if (this.data.showTyping) {
              this.setData({ showTyping: false, loadingTip: '' });
            }
            acc += frame.content;
            this._updateAssistantText(assistantIdx, acc);
            this._scrollToBottom();
          } else if (frame.type === 'recommendations') {
            try {
              const ids = (frame as any)?.content?.tmdb_ids;
              const title = (frame as any)?.content?.title;
              if (Array.isArray(ids) && ids.length) {
                const resp = await fetchMoviesBulk(
                  ids.map((x: any) => Number(x)).filter((x: any) => Number.isFinite(x)),
                );
                const cards = resp.items || [];
                const cardsTitle = typeof title === 'string' ? title : '为你推荐';
                if (assistantIdx >= this.data.messages.length) {
                  (this as any)._pendingMovieCards = cards;
                  (this as any)._pendingMovieCardsTitle = cardsTitle;
                } else {
                  this._updateAssistantMeta(assistantIdx, {
                    movie_cards: cards,
                    movie_cards_title: cardsTitle,
                  });
                }
              }
            } catch (_e) { }
          } else if (frame.type === 'complete') {
            const finalText = acc || frame.answer || '';
            this._updateAssistantText(assistantIdx, finalText);
            // Attach ids for feedback buttons (best-effort; depends on backend meta).
            const meta = (frame as any)?.meta;
            if (meta && typeof meta === 'object') {
              this._updateAssistantMeta(assistantIdx, {
                message_id: meta.message_id,
                thread_id: meta.thread_id,
                request_id: meta.request_id || frame.request_id,
                query: meta.query || userQuery,
                agent_type: meta.agent_type,
                feedback: 'none',
              });
            } else if (frame.request_id) {
              this._updateAssistantMeta(assistantIdx, {
                request_id: frame.request_id,
                query: userQuery,
                feedback: 'none',
              });
            }

            this.setData({ sending: false, loading: false, loadingTip: '', showTyping: false });
            // After the answer is completed, render the recommendations under this bubble (if any).
            // Reference-style: ids are attached to the final frame (response.extracted_info.recommendation_ids).
            try {
              const existingCards = this.data.messages?.[assistantIdx]?.movie_cards;
              const pendingCards = (this as any)._pendingMovieCards;
              if ((Array.isArray(existingCards) && existingCards.length) || (Array.isArray(pendingCards) && pendingCards.length)) {
                this._scrollToBottom();
                return;
              }
              const ids = (frame as any)?.response?.extracted_info?.recommendation_ids;
              const title = (frame as any)?.response?.extracted_info?.recommendation_title;
              if (Array.isArray(ids) && ids.length) {
                const resp = await fetchMoviesBulk(
                  ids.map((x: any) => Number(x)).filter((x: any) => Number.isFinite(x)),
                );
                this._updateAssistantMeta(assistantIdx, {
                  movie_cards: resp.items || [],
                  movie_cards_title: typeof title === 'string' ? title : '为你推荐',
                });
              }
            } catch (_e) { }
            this._scrollToBottom();
          }
        },
        onError: (_err: any) => {
          try {
            wx.showToast({ title: '请求失败（请检查后端是否启动/域名白名单）', icon: 'none' });
          } catch (_e) { }
          this.setData({ sending: false, loading: false, loadingTip: '', showTyping: false });
        },
        onComplete: () => {
          // Final state is handled by `complete`/`error` frames.
        },
      },
    );

    // Store task if you want cancel button later.
    (this as any)._activeTask = task;
  },

  _handleFrame(_frame: MpStreamFrame, _assistantIdx: number, _acc: string) { },

  _formatProgressTip(content: any): string {
    if (!content || typeof content !== 'object') {
      return '';
    }
    const stage = String((content as any).stage || '').toLowerCase();
    const selected = (content as any).selected_agent;
    if (stage === 'routing') {
      if (typeof selected === 'string' && selected.trim()) {
        return `正在路由（${selected.trim()}）…`;
      }
      return '正在路由…';
    }
    if (stage === 'recall') return '正在召回上下文…';
    if (stage === 'retrieval') return '正在检索资料…';
    if (stage === 'enrichment') return '正在补充外部信息…';
    if (stage === 'generation') return '正在生成回答…';
    // Fallback: show raw stage.
    return stage ? `处理中（${stage}）…` : '';
  },

  async onFeedback(e: any) {
    const d = e?.detail || {};
    const action = d.action;
    const messageId = d.message_id;
    const threadId = d.thread_id;
    const requestId = d.request_id;
    const query = d.query;
    const agentType = d.agent_type || 'hybrid_agent';

    if (action !== 'up' && action !== 'down') {
      return;
    }
    if (!messageId || !threadId || !query) {
      wx.showToast({ title: '该消息暂不支持反馈', icon: 'none' });
      return;
    }

    // Prevent spamming repeated requests for the same message.
    const pending = (this as any)._feedbackPending || {};
    if (pending[messageId]) {
      return;
    }
    pending[messageId] = true;
    (this as any)._feedbackPending = pending;

    try {
      const resp = await postFeedback({
        message_id: String(messageId),
        thread_id: String(threadId),
        query: String(query),
        is_positive: action === 'up',
        request_id: requestId ? String(requestId) : undefined,
        agent_type: String(agentType),
      });

      const fb = (resp && (resp as any).feedback) || 'none';
      this._setMessageFeedback(String(messageId), fb);
    } catch (_err) {
      wx.showToast({ title: '反馈失败', icon: 'none' });
    } finally {
      pending[messageId] = false;
      (this as any)._feedbackPending = pending;
    }
  },

  _updateAssistantText(idx: number, text: string) {
    // Check if assistant message exists
    if (idx >= this.data.messages.length) {
      // Create new assistant message
      const now = Date.now();
      const pendingCards = (this as any)._pendingMovieCards as MovieCard[] | undefined;
      const pendingTitle = (this as any)._pendingMovieCardsTitle as string | undefined;
      const assistantMsg: Msg = {
        role: 'assistant',
        text,
        timestamp: now,
        id: `msg-${now}`,
        timeStr: this._formatTime(now),
        showTime: false,
        feedback: 'none',
        message_id: '',
        thread_id: '',
        request_id: '',
        agent_type: '',
        query: '',
        movie_cards: Array.isArray(pendingCards) ? pendingCards : [],
        movie_cards_title: typeof pendingTitle === 'string' ? pendingTitle : '',
      };
      (this as any)._pendingMovieCards = undefined;
      (this as any)._pendingMovieCardsTitle = undefined;
      const messages = [...this.data.messages, assistantMsg];
      this.setData({ messages });
    } else {
      // Update existing message
      const key = `messages[${idx}].text`;
      this.setData({ [key]: text } as any);
    }
  },

  _updateAssistantMeta(idx: number, meta: Partial<Msg>) {
    if (idx >= this.data.messages.length) {
      // Ensure the assistant message exists first.
      this._updateAssistantText(idx, meta.text || '');
    }
    const updates: Record<string, any> = {};
    const keys: Array<keyof Msg> = [
      'message_id',
      'thread_id',
      'request_id',
      'query',
      'agent_type',
      'feedback',
      'movie_cards',
      'movie_cards_title',
    ];
    for (const k of keys) {
      let v = (meta as any)[k];
      if (v === null) {
        // Prevent null from being passed into typed component props.
        if (k === 'movie_cards') {
          v = [];
        } else if (k === 'feedback') {
          v = 'none';
        } else {
          v = '';
        }
      }
      if (typeof v !== 'undefined') {
        updates[`messages[${idx}].${String(k)}`] = v;
      }
    }
    if (Object.keys(updates).length) {
      this.setData(updates as any);
    }
  },

  _setMessageFeedback(messageId: string, feedback: 'positive' | 'negative' | 'none') {
    const msgs = this.data.messages || [];
    const idx = msgs.findIndex((m: any) => m && m.message_id === messageId);
    if (idx < 0) {
      return;
    }
    this.setData({ [`messages[${idx}].feedback`]: feedback } as any);
  },

  _formatTime(timestamp: number): string {
    const date = new Date(timestamp);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();

    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    if (isToday) {
      return `${hours}:${minutes}`;
    } else {
      const month = (date.getMonth() + 1).toString().padStart(2, '0');
      const day = date.getDate().toString().padStart(2, '0');
      return `${month}/${day} ${hours}:${minutes}`;
    }
  },

  _scrollToBottom() {
    // Force scroll by updating scrollTop (simple & stable for MVP).
    this.setData({ scrollTop: Date.now() });
  },

  onTapMovie(e: any) {
    const id = Number(e?.detail?.tmdb_id ?? e.currentTarget?.dataset?.id);
    if (!Number.isFinite(id)) {
      return;
    }
    wx.navigateTo({ url: `/pages/movie-detail/index?tmdb_id=${id}` });
  },
});
