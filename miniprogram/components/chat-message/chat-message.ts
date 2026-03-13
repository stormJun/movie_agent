Component({
  options: {
    multipleSlots: true,
    addGlobalClass: true,
  },

  properties: {
    role: {
      type: String,
      value: 'assistant', // 'user' | 'assistant'
    },
    text: {
      type: String,
      value: '',
    },
    suggestions: {
      type: Array,
      value: [],
    },
    theme: {
      type: String,
      value: 'light', // 'light' | 'dark'
    },
    showStatus: {
      type: Boolean,
      value: false,
    },
    statusType: {
      type: String,
      value: 'success', // 'loading' | 'success' | 'error'
    },
    statusText: {
      type: String,
      value: '',
    },
    statusIcon: {
      type: String,
      value: '',
    },
    statusSpinning: {
      type: Boolean,
      value: false,
    },

    // Feedback meta (optional; required to post /api/v1/feedback).
    messageId: {
      type: String,
      value: '',
    },
    threadId: {
      type: String,
      value: '',
    },
    requestId: {
      type: String,
      value: '',
    },
    agentType: {
      type: String,
      value: '',
    },
    query: {
      type: String,
      value: '',
    },
    // 'positive' | 'negative' | 'none'
    feedback: {
      type: String,
      value: 'none',
    },

    movieCards: {
      type: Array,
      value: [],
    },
    movieCardsTitle: {
      type: String,
      value: '',
    },
  },

  methods: {
    onTapSuggestion(e: any) {
      const text = e.currentTarget?.dataset?.text || '';
      if (!text) return;

      this.triggerEvent('suggestion', { text });
    },

    onTapStatus(e: any) {
      this.triggerEvent('status', {
        type: this.properties.statusType,
      });
    },

    onTapFeedback(e: any) {
      const action = e?.currentTarget?.dataset?.action;
      if (action !== 'up' && action !== 'down') {
        return;
      }
      this.triggerEvent('feedback', {
        action,
        message_id: this.properties.messageId,
        thread_id: this.properties.threadId,
        request_id: this.properties.requestId,
        agent_type: this.properties.agentType,
        query: this.properties.query,
        current: this.properties.feedback,
      });
    },

    onMovieTouchStart(e: any) {
      const t = e?.touches?.[0];
      const id = e?.currentTarget?.dataset?.id;
      if (!t || !id) return;
      // Record touch start so we can distinguish "tap" vs "swipe scroll".
      (this as any)._movieTouchStart = {
        x: Number(t.pageX),
        y: Number(t.pageY),
        ts: Date.now(),
        id,
      };
    },

    onMovieTouchEnd(e: any) {
      const start = (this as any)._movieTouchStart;
      (this as any)._movieTouchStart = null;
      const t = e?.changedTouches?.[0];
      if (!start || !t) return;

      const dx = Math.abs(Number(t.pageX) - Number(start.x));
      const dy = Math.abs(Number(t.pageY) - Number(start.y));
      const dt = Date.now() - Number(start.ts);

      // Heuristic: treat as a click only when the finger didn't move (otherwise it's a scroll).
      // Keep thresholds small so horizontal swipe still works.
      const isTap = dx <= 8 && dy <= 8 && dt <= 600;
      if (!isTap) return;

      this.triggerEvent('movie', { tmdb_id: start.id });
    },
  },
});
