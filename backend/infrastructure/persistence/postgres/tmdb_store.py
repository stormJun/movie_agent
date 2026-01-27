from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def _jsonb_dumps(value: Any) -> str:
    # Keep encoding consistent with other Postgres JSONB stores.
    return json.dumps(value, ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    # Stable hashing for JSON snapshots; used for ETL incremental sync.
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class PostgresTmdbStore:
    """PostgreSQL TMDB persistence store (asyncpg).

    This store persists:
      - Latest snapshots for TMDB entities (movie/person/tv) as raw JSONB (+ a raw_hash)
      - Enrichment request logs (search/discover raw results + disambiguation metadata)
      - Neo4j ETL outbox tasks keyed by (entity_type, tmdb_id, raw_hash)

    The schema is best-effort bootstrapped at runtime for local/dev. Production
    deployments should manage schema via migrations.
    """

    def __init__(
        self,
        *,
        dsn: str,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool = None
        self._pool_lock = asyncio.Lock()

    async def _get_pool(self):
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is not None:
                return self._pool
            import asyncpg  # type: ignore

            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                ssl=False,
            )
            await self._ensure_schema()
            logger.info("PostgreSQL TMDB store pool initialized")
            return self._pool

    async def _ensure_schema(self) -> None:
        pool = self._pool
        if pool is None:
            return
        async with pool.acquire() as conn:
            # Needed for gen_random_uuid().
            try:
                await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
            except Exception as e:
                logger.warning("tmdb schema: failed to ensure pgcrypto extension: %s", e)

            await conn.execute("CREATE SCHEMA IF NOT EXISTS tmdb;")

            # Movies.
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.movies (
                  tmdb_id            int PRIMARY KEY,
                  title              text,
                  original_title     text,
                  original_language  text,
                  release_date       date,
                  popularity         double precision,
                  vote_average       double precision,
                  vote_count         int,
                  raw_language       text NOT NULL DEFAULT 'zh-CN',
                  data_state         text NOT NULL DEFAULT 'full' CHECK (data_state IN ('stub','full')),
                  raw                jsonb,
                  raw_hash           text,
                  fetched_at         timestamptz NOT NULL DEFAULT now(),
                  first_seen_at      timestamptz NOT NULL DEFAULT now(),
                  last_seen_at       timestamptz NOT NULL DEFAULT now(),
                  CONSTRAINT ck_tmdb_movies_state
                    CHECK (
                      (data_state = 'stub' AND raw IS NULL AND raw_hash IS NULL)
                      OR
                      (data_state = 'full' AND raw IS NOT NULL AND raw_hash IS NOT NULL)
                    )
                );
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.movie_translations (
                  tmdb_movie_id  int NOT NULL REFERENCES tmdb.movies(tmdb_id) ON DELETE CASCADE,
                  language       text NOT NULL,
                  title          text,
                  overview       text,
                  raw            jsonb,
                  raw_hash       text,
                  fetched_at     timestamptz NOT NULL DEFAULT now(),
                  first_seen_at  timestamptz NOT NULL DEFAULT now(),
                  last_seen_at   timestamptz NOT NULL DEFAULT now(),
                  PRIMARY KEY (tmdb_movie_id, language)
                );
                """
            )

            # People.
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.people (
                  tmdb_id               int PRIMARY KEY,
                  name                  text,
                  original_name         text,
                  known_for_department  text,
                  popularity            double precision,
                  raw_language          text NOT NULL DEFAULT 'zh-CN',
                  data_state            text NOT NULL DEFAULT 'full' CHECK (data_state IN ('stub','full')),
                  raw                   jsonb,
                  raw_hash              text,
                  fetched_at            timestamptz NOT NULL DEFAULT now(),
                  first_seen_at         timestamptz NOT NULL DEFAULT now(),
                  last_seen_at          timestamptz NOT NULL DEFAULT now(),
                  CONSTRAINT ck_tmdb_people_state
                    CHECK (
                      (data_state = 'stub' AND raw IS NULL AND raw_hash IS NULL)
                      OR
                      (data_state = 'full' AND raw IS NOT NULL AND raw_hash IS NOT NULL)
                    )
                );
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.person_translations (
                  tmdb_person_id  int NOT NULL REFERENCES tmdb.people(tmdb_id) ON DELETE CASCADE,
                  language        text NOT NULL,
                  biography       text,
                  raw             jsonb,
                  raw_hash        text,
                  fetched_at      timestamptz NOT NULL DEFAULT now(),
                  first_seen_at   timestamptz NOT NULL DEFAULT now(),
                  last_seen_at    timestamptz NOT NULL DEFAULT now(),
                  PRIMARY KEY (tmdb_person_id, language)
                );
                """
            )

            # TV shows.
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.tv_shows (
                  tmdb_id            int PRIMARY KEY,
                  name               text,
                  original_name      text,
                  original_language  text,
                  first_air_date     date,
                  popularity         double precision,
                  vote_average       double precision,
                  vote_count         int,
                  raw_language       text NOT NULL DEFAULT 'zh-CN',
                  data_state         text NOT NULL DEFAULT 'full' CHECK (data_state IN ('stub','full')),
                  raw                jsonb,
                  raw_hash           text,
                  fetched_at         timestamptz NOT NULL DEFAULT now(),
                  first_seen_at      timestamptz NOT NULL DEFAULT now(),
                  last_seen_at       timestamptz NOT NULL DEFAULT now(),
                  CONSTRAINT ck_tmdb_tv_shows_state
                    CHECK (
                      (data_state = 'stub' AND raw IS NULL AND raw_hash IS NULL)
                      OR
                      (data_state = 'full' AND raw IS NOT NULL AND raw_hash IS NOT NULL)
                    )
                );
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.tv_translations (
                  tmdb_tv_id     int NOT NULL REFERENCES tmdb.tv_shows(tmdb_id) ON DELETE CASCADE,
                  language       text NOT NULL,
                  name           text,
                  overview       text,
                  raw            jsonb,
                  raw_hash       text,
                  fetched_at     timestamptz NOT NULL DEFAULT now(),
                  first_seen_at  timestamptz NOT NULL DEFAULT now(),
                  last_seen_at   timestamptz NOT NULL DEFAULT now(),
                  PRIMARY KEY (tmdb_tv_id, language)
                );
                """
            )

            # Enrichment requests.
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.enrichment_requests (
                  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                  request_id          text,
                  user_id             text NOT NULL,
                  session_id          text NOT NULL,
                  conversation_id     uuid,
                  user_message_id     uuid,
                  query_text          text NOT NULL,
                  tmdb_endpoint       text NOT NULL DEFAULT '/search/multi',
                  role_hint           text,
                  extracted_entities  jsonb,
                  selected            jsonb,
                  selected_media_type text,
                  selected_tmdb_id    int,
                  selected_score      double precision,
                  candidates_top3     jsonb,
                  multi_results_raw   jsonb,
                  discover_results_raw jsonb,
                  tmdb_language       text,
                  duration_ms         double precision,
                  created_at          timestamptz NOT NULL DEFAULT now()
                );
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tmdb_enrich_req_created
                ON tmdb.enrichment_requests(created_at DESC);
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tmdb_enrich_req_user
                ON tmdb.enrichment_requests(user_id, created_at DESC);
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tmdb_enrich_req_selected
                ON tmdb.enrichment_requests(selected_media_type, selected_tmdb_id);
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tmdb_enrich_req_endpoint
                ON tmdb.enrichment_requests(tmdb_endpoint, created_at DESC);
                """
            )

            # ETL outbox.
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.neo4j_etl_outbox (
                  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                  entity_type     text NOT NULL CHECK (entity_type IN ('movie','person','tv')),
                  tmdb_id         int  NOT NULL,
                  raw_hash        text NOT NULL,
                  action          text NOT NULL DEFAULT 'upsert' CHECK (action IN ('upsert','delete')),
                  request_id      text,
                  enqueued_at     timestamptz NOT NULL DEFAULT now(),
                  locked_at       timestamptz,
                  attempts        int NOT NULL DEFAULT 0,
                  last_attempt_at timestamptz,
                  last_error      text,
                  processed_at    timestamptz
                );
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tmdb_etl_outbox_pending
                ON tmdb.neo4j_etl_outbox(processed_at, enqueued_at);
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tmdb_etl_outbox_entity
                ON tmdb.neo4j_etl_outbox(entity_type, tmdb_id);
                """
            )
            await conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_tmdb_etl_outbox_dedupe
                ON tmdb.neo4j_etl_outbox(entity_type, tmdb_id, raw_hash, action);
                """
            )

            # Optional: request -> entities mapping (for analysis).
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tmdb.enrichment_request_entities (
                  enrichment_request_id uuid NOT NULL REFERENCES tmdb.enrichment_requests(id) ON DELETE CASCADE,
                  entity_type           text NOT NULL CHECK (entity_type IN ('movie','person','tv')),
                  tmdb_id               int  NOT NULL,
                  selected              boolean NOT NULL DEFAULT false,
                  score                 double precision,
                  PRIMARY KEY (enrichment_request_id, entity_type, tmdb_id)
                );
                """
            )

    async def close(self) -> None:
        pool = self._pool
        if pool is None:
            return
        await pool.close()

    async def persist_enrichment(
        self,
        *,
        user_id: str,
        session_id: str,
        query_text: str,
        tmdb_endpoint: str,
        extracted_entities: list[str] | None,
        disambiguation: list[dict[str, Any]] | None,
        payloads: list[dict[str, Any]] | None,
        request_id: str | None = None,
        conversation_id: UUID | None = None,
        user_message_id: UUID | None = None,
        candidates_top3: Any | None = None,
        multi_results_raw: Any | None = None,
        discover_results_raw: Any | None = None,
        role_hint: str | None = None,
        tmdb_language: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Persist one enrichment run (best-effort)."""
        if not user_id or not session_id or not query_text:
            return

        pool = await self._get_pool()
        disamb = disambiguation if isinstance(disambiguation, list) else []
        payloads = payloads if isinstance(payloads, list) else []

        # If the request effectively resolved a single entity, populate fast-path columns.
        selected_media_type: str | None = None
        selected_tmdb_id: int | None = None
        selected_score: float | None = None
        selected_count = 0
        for meta in disamb:
            if not isinstance(meta, dict):
                continue
            sel = meta.get("selected")
            media_type = str(meta.get("type") or "").strip().lower()
            if isinstance(sel, dict) and sel.get("id") is not None and media_type in {"movie", "person", "tv"}:
                selected_count += 1
                selected_media_type = media_type
                try:
                    selected_tmdb_id = int(sel.get("id"))
                except Exception:
                    selected_tmdb_id = None
                try:
                    selected_score = float(sel.get("score")) if sel.get("score") is not None else None
                except Exception:
                    selected_score = None
        if selected_count != 1:
            selected_media_type = None
            selected_tmdb_id = None
            selected_score = None

        # Upsert entities and enqueue ETL if raw changed.
        async with pool.acquire() as conn:
            req_row = await conn.fetchrow(
                """
                INSERT INTO tmdb.enrichment_requests (
                  request_id,
                  user_id,
                  session_id,
                  conversation_id,
                  user_message_id,
                  query_text,
                  tmdb_endpoint,
                  role_hint,
                  extracted_entities,
                  selected,
                  selected_media_type,
                  selected_tmdb_id,
                  selected_score,
                  candidates_top3,
                  multi_results_raw,
                  discover_results_raw,
                  tmdb_language,
                  duration_ms
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11,$12,$13,$14::jsonb,$15::jsonb,$16::jsonb,$17,$18)
                RETURNING id
                """,
                request_id,
                user_id,
                session_id,
                conversation_id,
                user_message_id,
                query_text,
                tmdb_endpoint or "/search/multi",
                role_hint,
                _jsonb_dumps(extracted_entities or []) if extracted_entities is not None else None,
                _jsonb_dumps(disamb) if disambiguation is not None else None,
                selected_media_type,
                selected_tmdb_id,
                selected_score,
                _jsonb_dumps(candidates_top3) if candidates_top3 is not None else None,
                _jsonb_dumps(multi_results_raw) if multi_results_raw is not None else None,
                _jsonb_dumps(discover_results_raw) if discover_results_raw is not None else None,
                tmdb_language,
                float(duration_ms) if duration_ms is not None else None,
            )
            enrichment_request_id = req_row["id"] if req_row else None

            selected_set: set[tuple[str, int]] = set()
            score_map: dict[tuple[str, int], float] = {}
            for meta in disamb:
                if not isinstance(meta, dict):
                    continue
                sel = meta.get("selected")
                media_type = str(meta.get("type") or "").strip().lower()
                if not isinstance(sel, dict):
                    continue
                if sel.get("id") is None:
                    continue
                if media_type not in {"movie", "person", "tv"}:
                    continue
                try:
                    tid = int(sel.get("id"))
                except Exception:
                    continue
                selected_set.add((media_type, tid))
                try:
                    sc = float(sel.get("score")) if sel.get("score") is not None else None
                except Exception:
                    sc = None
                if sc is not None:
                    score_map[(media_type, tid)] = sc

            for payload in payloads:
                if not isinstance(payload, dict):
                    continue
                p_type = str(payload.get("type") or "").strip().lower()
                data = payload.get("data")
                if p_type not in {"movie", "person", "tv"}:
                    continue
                if not isinstance(data, dict) or not data:
                    continue
                tmdb_id = data.get("id")
                if tmdb_id is None:
                    continue
                try:
                    tmdb_id_int = int(tmdb_id)
                except Exception:
                    continue

                raw_hash = _sha256_json(data)

                # Read current hash for change detection.
                if p_type == "movie":
                    current = await conn.fetchval("SELECT raw_hash FROM tmdb.movies WHERE tmdb_id=$1", tmdb_id_int)
                    await conn.execute(
                        """
                        INSERT INTO tmdb.movies (
                          tmdb_id, title, original_title, original_language, release_date,
                          popularity, vote_average, vote_count, raw_language, data_state,
                          raw, raw_hash, fetched_at, last_seen_at
                        )
                        VALUES (
                          $1,$2,$3,$4,NULLIF($5,'')::date,
                          $6,$7,$8,$9,'full',
                          $10::jsonb,$11,now(),now()
                        )
                        ON CONFLICT (tmdb_id) DO UPDATE SET
                          title=EXCLUDED.title,
                          original_title=EXCLUDED.original_title,
                          original_language=EXCLUDED.original_language,
                          release_date=EXCLUDED.release_date,
                          popularity=EXCLUDED.popularity,
                          vote_average=EXCLUDED.vote_average,
                          vote_count=EXCLUDED.vote_count,
                          raw_language=EXCLUDED.raw_language,
                          data_state='full',
                          raw=EXCLUDED.raw,
                          raw_hash=EXCLUDED.raw_hash,
                          fetched_at=EXCLUDED.fetched_at,
                          last_seen_at=now()
                        """,
                        tmdb_id_int,
                        (data.get("title") or None),
                        (data.get("original_title") or None),
                        (data.get("original_language") or None),
                        (data.get("release_date") or ""),
                        data.get("popularity"),
                        data.get("vote_average"),
                        data.get("vote_count"),
                        "zh-CN",
                        _jsonb_dumps(data),
                        raw_hash,
                    )
                elif p_type == "person":
                    current = await conn.fetchval("SELECT raw_hash FROM tmdb.people WHERE tmdb_id=$1", tmdb_id_int)
                    await conn.execute(
                        """
                        INSERT INTO tmdb.people (
                          tmdb_id, name, original_name, known_for_department, popularity,
                          raw_language, data_state, raw, raw_hash, fetched_at, last_seen_at
                        )
                        VALUES (
                          $1,$2,$3,$4,$5,
                          $6,'full',$7::jsonb,$8,now(),now()
                        )
                        ON CONFLICT (tmdb_id) DO UPDATE SET
                          name=EXCLUDED.name,
                          original_name=EXCLUDED.original_name,
                          known_for_department=EXCLUDED.known_for_department,
                          popularity=EXCLUDED.popularity,
                          raw_language=EXCLUDED.raw_language,
                          data_state='full',
                          raw=EXCLUDED.raw,
                          raw_hash=EXCLUDED.raw_hash,
                          fetched_at=EXCLUDED.fetched_at,
                          last_seen_at=now()
                        """,
                        tmdb_id_int,
                        (data.get("name") or None),
                        (data.get("original_name") or None),
                        (data.get("known_for_department") or None),
                        data.get("popularity"),
                        "zh-CN",
                        _jsonb_dumps(data),
                        raw_hash,
                    )
                else:
                    current = await conn.fetchval("SELECT raw_hash FROM tmdb.tv_shows WHERE tmdb_id=$1", tmdb_id_int)
                    await conn.execute(
                        """
                        INSERT INTO tmdb.tv_shows (
                          tmdb_id, name, original_name, original_language, first_air_date,
                          popularity, vote_average, vote_count, raw_language, data_state,
                          raw, raw_hash, fetched_at, last_seen_at
                        )
                        VALUES (
                          $1,$2,$3,$4,NULLIF($5,'')::date,
                          $6,$7,$8,$9,'full',
                          $10::jsonb,$11,now(),now()
                        )
                        ON CONFLICT (tmdb_id) DO UPDATE SET
                          name=EXCLUDED.name,
                          original_name=EXCLUDED.original_name,
                          original_language=EXCLUDED.original_language,
                          first_air_date=EXCLUDED.first_air_date,
                          popularity=EXCLUDED.popularity,
                          vote_average=EXCLUDED.vote_average,
                          vote_count=EXCLUDED.vote_count,
                          raw_language=EXCLUDED.raw_language,
                          data_state='full',
                          raw=EXCLUDED.raw,
                          raw_hash=EXCLUDED.raw_hash,
                          fetched_at=EXCLUDED.fetched_at,
                          last_seen_at=now()
                        """,
                        tmdb_id_int,
                        (data.get("name") or None),
                        (data.get("original_name") or None),
                        (data.get("original_language") or None),
                        (data.get("first_air_date") or ""),
                        data.get("popularity"),
                        data.get("vote_average"),
                        data.get("vote_count"),
                        "zh-CN",
                        _jsonb_dumps(data),
                        raw_hash,
                    )

                # Enqueue ETL only on changes (or first insert).
                if current != raw_hash:
                    await conn.execute(
                        """
                        INSERT INTO tmdb.neo4j_etl_outbox (entity_type, tmdb_id, raw_hash, action, request_id)
                        VALUES ($1,$2,$3,'upsert',$4)
                        ON CONFLICT DO NOTHING
                        """,
                        p_type,
                        tmdb_id_int,
                        raw_hash,
                        request_id,
                    )

                # Optional mapping row for analysis.
                if enrichment_request_id is not None:
                    is_selected = (p_type, tmdb_id_int) in selected_set
                    score = score_map.get((p_type, tmdb_id_int))
                    await conn.execute(
                        """
                        INSERT INTO tmdb.enrichment_request_entities (
                          enrichment_request_id, entity_type, tmdb_id, selected, score
                        )
                        VALUES ($1,$2,$3,$4,$5)
                        ON CONFLICT (enrichment_request_id, entity_type, tmdb_id)
                        DO UPDATE SET selected=EXCLUDED.selected, score=EXCLUDED.score
                        """,
                        enrichment_request_id,
                        p_type,
                        tmdb_id_int,
                        bool(is_selected),
                        score,
                    )

