import { fetchMovieDetail, MovieDetail } from '../../utils/api';

Page({
  data: {
    movie: null as MovieDetail | null,
    errorText: '',
  },

  async onLoad(options: any) {
    const id = Number(options?.tmdb_id);
    if (!Number.isFinite(id)) {
      this.setData({ errorText: '无效的电影 ID' });
      return;
    }
    try {
      const resp = await fetchMovieDetail(id);
      const m: any = resp.movie || null;
      if (!m) {
        this.setData({ movie: null, errorText: '加载失败（空响应）' });
        return;
      }

      // WXML 不支持直接调用 JS 方法（例如 arr.join / num.toFixed），这里预先计算展示文本。
      const directors = Array.isArray(m.directors) ? m.directors : [];
      const genres = Array.isArray(m.genres) ? m.genres : [];
      const voteAverage = typeof m.vote_average === 'number' ? m.vote_average : null;
      const runtime = typeof m.runtime === 'number' ? m.runtime : null;
      const year = typeof m.year === 'number' ? m.year : null;

      m.directors_text = directors.join(' / ');
      m.genres_text = genres.join(' / ');
      m.vote_average_text = voteAverage !== null ? voteAverage.toFixed(1) : '';
      m.meta_text = [
        year ? String(year) : '',
        runtime ? `${runtime}min` : '',
        voteAverage !== null ? `${voteAverage.toFixed(1)}分` : '',
      ]
        .filter(Boolean)
        .join(' · ');

      this.setData({ movie: m as MovieDetail, errorText: '' });
    } catch (_e) {
      this.setData({ errorText: '加载失败（本地库可能还没有该条目）' });
    }
  },
});
