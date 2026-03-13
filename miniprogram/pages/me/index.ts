import { getApiBaseUrl } from '../../utils/config';

Page({
  data: {
    userId: '',
    sessionId: '',
    shortUserId: '',
    shortSessionId: '',
    baseUrl: '',
  },

  onLoad() {
    this.setData({ baseUrl: getApiBaseUrl() });
    const userId = wx.getStorageSync('mp_user_id') || '';
    const sessionId = wx.getStorageSync('mp_session_id') || '';

    this.setData({
      userId,
      sessionId,
      shortUserId: userId ? `${userId.substring(0, 8)}...` : '未设置',
      shortSessionId: sessionId ? `${sessionId.substring(0, 8)}...` : '未设置',
    });
  },

  onShow() {
    const userId = wx.getStorageSync('mp_user_id') || '';
    const sessionId = wx.getStorageSync('mp_session_id') || '';
    this.setData({
      baseUrl: getApiBaseUrl(),
      userId,
      sessionId,
      shortUserId: userId ? `${userId.substring(0, 8)}...` : '未设置',
      shortSessionId: sessionId ? `${sessionId.substring(0, 8)}...` : '未设置',
    });
  },

  onCopyUserId() {
    const { userId } = this.data;
    if (!userId) {
      wx.showToast({
        title: '用户ID不存在',
        icon: 'none',
      });
      return;
    }

    wx.setClipboardData({
      data: userId,
      success: () => {
        wx.showToast({
          title: '已复制',
          icon: 'success',
        });
      },
    });
  },

  onCopySessionId() {
    const { sessionId } = this.data;
    if (!sessionId) {
      wx.showToast({
        title: '会话ID不存在',
        icon: 'none',
      });
      return;
    }

    wx.setClipboardData({
      data: sessionId,
      success: () => {
        wx.showToast({
          title: '已复制',
          icon: 'success',
        });
      },
    });
  },

  onCopyBaseUrl() {
    const { baseUrl } = this.data;

    wx.setClipboardData({
      data: baseUrl,
      success: () => {
        wx.showToast({
          title: '已复制',
          icon: 'success',
        });
      },
    });
  },

  onResetSession() {
    wx.showModal({
      title: '确认清空？',
      content: '将清空本地聊天记录，并生成新的会话。',
      confirmText: '确认',
      cancelText: '取消',
      confirmColor: '#5D45FA',
      success: (res) => {
        if (res.confirm) {
          // Generate new session ID
          const newSessionId = `s_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
          wx.setStorageSync('mp_session_id', newSessionId);

          // Clear messages by navigating to chat
          wx.switchTab({
            url: '/pages/chat/index',
            success: () => {
              wx.showToast({
                title: '会话已重置',
                icon: 'success',
              });
            },
          });
        }
      },
    });
  },
});
