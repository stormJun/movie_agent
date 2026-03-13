import { mpApi } from './config';
import { httpGet, httpPost } from './http';

export type MovieCard = {
  tmdb_id: number;
  title: string;
  release_date?: string | null;
  year?: number | null;
  poster_url?: string | null;
  vote_average?: number | null;
  vote_count?: number | null;
  popularity?: number | null;
  directors?: string[];
  top_cast?: string[];
  genres?: string[];
};

export type MovieDetail = MovieCard & {
  original_title?: string | null;
  overview?: string | null;
  backdrop_url?: string | null;
  runtime?: number | null;
  cast?: Array<{ name: string; character?: string | null }>;
  crew?: Array<{ name: string; job: string }>;
};

export async function fetchMoviesFeed(params: {
  type: 'popular' | 'now_playing' | 'upcoming';
  limit?: number;
  offset?: number;
}): Promise<{ items: MovieCard[]; next_offset: number }> {
  const qs = `type=${encodeURIComponent(params.type)}&limit=${params.limit ?? 20}&offset=${params.offset ?? 0}`;
  return httpGet(mpApi(`/api/v1/mp/movies/feed?${qs}`));
}

export async function fetchMovieDetail(tmdbId: number): Promise<{ movie: MovieDetail }> {
  return httpGet(mpApi(`/api/v1/mp/movies/${tmdbId}`));
}

export async function fetchMoviesBulk(ids: number[]): Promise<{ items: MovieCard[]; missing_ids: number[] }> {
  return httpPost(mpApi(`/api/v1/mp/movies/bulk`), { ids });
}

export type FeedbackResponse = {
  status: string;
  action: string;
  feedback?: 'positive' | 'negative' | 'none' | null;
};

export async function postFeedback(params: {
  message_id: string;
  thread_id: string;
  query: string;
  is_positive: boolean;
  request_id?: string;
  agent_type?: string;
}): Promise<FeedbackResponse> {
  return httpPost(mpApi(`/api/v1/mp/feedback`), params);
}
