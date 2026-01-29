"""TMDB offline backfill utilities.

This integration exists to re-hydrate incomplete tmdb.movies snapshots in Postgres
with full /movie/{id}?append_to_response=credits payloads (director/cast/genres).
"""

