import { fetchMoviesFeed, MovieCard } from '../../utils/api';

function decorateMovieCard(item: MovieCard): any {
  const year = typeof (item as any).year === 'number' ? (item as any).year : null;
  const voteAverage = typeof (item as any).vote_average === 'number' ? (item as any).vote_average : null;
  const voteCount = typeof (item as any).vote_count === 'number' ? (item as any).vote_count : null;
  const parts: string[] = [];
  if (year) {
    parts.push(String(year));
  }
  // Avoid showing "0.0" for titles without enough votes (common for upcoming).
  if (voteAverage !== null && voteAverage > 0 && voteCount !== null && voteCount > 0) {
    parts.push(voteAverage.toFixed(1));
  }
  return { ...item, meta_text: parts.join(' · ') };
}

Page({
  data: {
    feedType: 'popular' as 'popular' | 'now_playing' | 'upcoming',
    items: [] as MovieCard[],
    offset: 0,
    loading: false,
    errorText: '',
    navBarHeight: 0,
  },

  onLoad() {
    // Match reference approach: derive nav bar height from the capsule button geometry.
    // This avoids hardcoded "statusBar + 44" mismatches across devices.
    const windowInfo = (wx as any).getWindowInfo?.() || wx.getSystemInfoSync();
    const statusBarHeight = windowInfo.statusBarHeight || 20;
    const menu = wx.getMenuButtonBoundingClientRect();
    const navBarHeight = statusBarHeight + menu.height + (menu.top - statusBarHeight) * 2;
    this.setData({ navBarHeight });

    this._reload();
  },

  async onSwitch(e: any) {
    const t = e.currentTarget?.dataset?.type as any;
    if (t !== 'popular' && t !== 'now_playing' && t !== 'upcoming') {
      return;
    }
    if (t === this.data.feedType) {
      return;
    }
    this.setData({ feedType: t });
    await this._reload();
  },

  async _reload() {
    this.setData({ items: [], offset: 0, loading: true, errorText: '' });
    try {
      const resp = await fetchMoviesFeed({ type: this.data.feedType, limit: 24, offset: 0 });
      const items = (resp.items || []).map(decorateMovieCard);
      // Show empty state if no items returned
      const errorText = items.length === 0 ? '暂无数据（请稍后重试）' : '';
      this.setData({ items, offset: resp.next_offset || 0, loading: false, errorText });
    } catch (_e) {
      const msg = (_e as any)?.message || '加载失败，请检查后端是否启动 / 是否允许请求本地域名';
      this.setData({ loading: false, errorText: msg });
      try {
        wx.showToast({ title: '加载失败', icon: 'none' });
      } catch (_err) {}
    }
  },

  async onLoadMore() {
    if (this.data.loading) {
      return;
    }
    this.setData({ loading: true });
    try {
      const resp = await fetchMoviesFeed({ type: this.data.feedType, limit: 24, offset: this.data.offset });
      this.setData({
        items: [...this.data.items, ...(resp.items || []).map(decorateMovieCard)],
        offset: resp.next_offset || this.data.offset,
        loading: false,
      });
    } catch (_e) {
      const msg = (_e as any)?.message || '加载失败';
      this.setData({ loading: false, errorText: msg });
    }
  },

  onTapMovie(e: any) {
    const id = Number(e.currentTarget?.dataset?.id);
    if (!Number.isFinite(id)) {
      return;
    }
    wx.navigateTo({ url: `/pages/movie-detail/index?tmdb_id=${id}` });
  },
});
