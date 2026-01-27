"""
Graph builder for converting TMDB API data into TransientGraph structures.

This module transforms raw TMDB movie data into structured graph representations
that can be fused with GraphRAG retrieval results.
"""

from __future__ import annotations

import logging
from typing import Any

from infrastructure.enrichment.models import TransientEdge, TransientGraph, TransientNode

logger = logging.getLogger(__name__)


class TransientGraphBuilder:
    """Build TransientGraph from TMDB API data.

    This builder converts TMDB movie details into a graph structure with:
    - Movie nodes (title, overview, release date, rating)
    - Person nodes (directors, actors)
    - Genre nodes
    - Relationship edges (DIRECTED, ACTED_IN, BELONGS_TO_GENRE)
    """

    def build_from_tmdb_data(self, movie_data_list: list[dict[str, Any]]) -> TransientGraph:
        """Build a transient graph from TMDB movie data.

        Args:
            movie_data_list: List of movie detail dictionaries from TMDB API

        Returns:
            A TransientGraph containing all nodes and edges extracted from the movies.
        """
        payloads: list[dict[str, Any]] = []
        for movie_data in movie_data_list:
            if isinstance(movie_data, dict) and movie_data:
                payloads.append({"type": "movie", "data": movie_data})

        graph = self.build_from_tmdb_payloads(payloads)

        logger.info(
            f"Built TransientGraph: {len(graph.nodes)} nodes, " f"{len(graph.edges)} edges"
        )

        return graph

    def build_from_tmdb_payloads(self, payloads: list[dict[str, Any]]) -> TransientGraph:
        """Build a transient graph from mixed TMDB payloads (movies and people)."""
        graph = TransientGraph()
        # Deduplicate nodes/edges to keep context readable.
        node_ids: set[str] = set()
        edge_keys: set[tuple[str, str, str]] = set()

        for payload in payloads or []:
            if not isinstance(payload, dict):
                continue
            p_type = str(payload.get("type") or "").strip()
            data = payload.get("data")
            if not isinstance(data, dict) or not data:
                continue
            if p_type == "movie":
                self._add_movie_to_graph(graph, data, node_ids=node_ids, edge_keys=edge_keys)
            elif p_type == "tv":
                self._add_tv_to_graph(graph, data, node_ids=node_ids, edge_keys=edge_keys)
            elif p_type == "person":
                self._add_person_to_graph(graph, data, node_ids=node_ids, edge_keys=edge_keys)

        return graph

    def _add_node(
        self, graph: TransientGraph, node: TransientNode, *, node_ids: set[str]
    ) -> None:
        if node.id in node_ids:
            return
        node_ids.add(node.id)
        graph.nodes.append(node)

    def _add_edge(
        self,
        graph: TransientGraph,
        edge: TransientEdge,
        *,
        edge_keys: set[tuple[str, str, str]],
    ) -> None:
        key = (edge.source, edge.target, edge.relationship_type)
        if key in edge_keys:
            return
        edge_keys.add(key)
        graph.edges.append(edge)

    def _add_movie_to_graph(
        self,
        graph: TransientGraph,
        movie_data: dict[str, Any],
        *,
        node_ids: set[str],
        edge_keys: set[tuple[str, str, str]],
    ) -> None:
        """Add a single movie and its related entities to the graph.

        This method extracts:
        - The movie node
        - Director nodes and DIRECTED edges
        - Actor nodes and ACTED_IN edges
        - Genre nodes and BELONGS_TO_GENRE edges

        Args:
            graph: The TransientGraph to add data to
            movie_data: Movie detail dictionary from TMDB API
        """
        # 1. Create movie node
        movie_id = movie_data.get("id")
        movie_title = movie_data.get("title", "")
        movie_overview = movie_data.get("overview", "")
        movie_release_date = movie_data.get("release_date", "")
        movie_rating = movie_data.get("vote_average", 0.0)

        movie_node = TransientNode(
            id=f"tmdb:movie:{movie_id}",
            labels={"Movie", "Entity"},
            properties={
                "name": movie_title,
                "description": movie_overview,
                "release_date": movie_release_date,
                "rating": movie_rating,
                "source": "tmdb",
                "tmdb_id": movie_id,
            },
        )
        self._add_node(graph, movie_node, node_ids=node_ids)

        # 2. Extract director information
        credits = movie_data.get("credits", {})
        crew = credits.get("crew", [])

        directors = [person for person in crew if person.get("job") == "Director"]

        for director in directors[:3]:  # Limit to top 3 directors
            director_id = director.get("id")
            director_name = director.get("name", "")

            director_node = TransientNode(
                id=f"tmdb:person:{director_id}",
                labels={"Person", "Director", "Entity"},
                properties={
                    "name": director_name,
                    "source": "tmdb",
                    "tmdb_id": director_id,
                },
            )
            self._add_node(graph, director_node, node_ids=node_ids)

            # Director -> Movie edge
            self._add_edge(
                graph,
                TransientEdge(
                    source=director_node.id,
                    target=movie_node.id,
                    relationship_type="DIRECTED",
                    properties={"source": "tmdb"},
                ),
                edge_keys=edge_keys,
            )

        # 3. Extract top cast members
        cast = credits.get("cast", [])
        for actor in cast[:5]:  # Limit to top 5 actors
            actor_id = actor.get("id")
            actor_name = actor.get("name", "")
            character_name = actor.get("character", "")

            actor_node = TransientNode(
                id=f"tmdb:person:{actor_id}",
                labels={"Person", "Actor", "Entity"},
                properties={
                    "name": actor_name,
                    "character": character_name,
                    "source": "tmdb",
                    "tmdb_id": actor_id,
                },
            )
            self._add_node(graph, actor_node, node_ids=node_ids)

            # Actor -> Movie edge
            self._add_edge(
                graph,
                TransientEdge(
                    source=actor_node.id,
                    target=movie_node.id,
                    relationship_type="ACTED_IN",
                    properties={"character": character_name, "source": "tmdb"},
                ),
                edge_keys=edge_keys,
            )

        # 4. Extract genres
        genres = movie_data.get("genres", [])
        for genre in genres:
            genre_id = genre.get("id")
            genre_name = genre.get("name", "")

            genre_node = TransientNode(
                id=f"tmdb:genre:{genre_id}",
                labels={"Genre", "Entity"},
                properties={
                    "name": genre_name,
                    "source": "tmdb",
                },
            )
            self._add_node(graph, genre_node, node_ids=node_ids)

            # Movie -> Genre edge
            self._add_edge(
                graph,
                TransientEdge(
                    source=movie_node.id,
                    target=genre_node.id,
                    relationship_type="BELONGS_TO_GENRE",
                    properties={"source": "tmdb"},
                ),
                edge_keys=edge_keys,
            )

    def _add_tv_to_graph(
        self,
        graph: TransientGraph,
        tv_data: dict[str, Any],
        *,
        node_ids: set[str],
        edge_keys: set[tuple[str, str, str]],
    ) -> None:
        """Add a single TV show and its related entities to the graph."""
        tv_id = tv_data.get("id")
        tv_name = tv_data.get("name", "")
        tv_overview = tv_data.get("overview", "")
        tv_first_air_date = tv_data.get("first_air_date", "")
        tv_rating = tv_data.get("vote_average", 0.0)

        tv_node = TransientNode(
            id=f"tmdb:tv:{tv_id}",
            labels={"TV", "Entity"},
            properties={
                "name": tv_name,
                "description": tv_overview,
                "first_air_date": tv_first_air_date,
                "rating": tv_rating,
                "source": "tmdb",
                "tmdb_id": tv_id,
            },
        )
        self._add_node(graph, tv_node, node_ids=node_ids)

        credits = tv_data.get("credits", {}) or {}
        crew = credits.get("crew", []) or []
        cast = credits.get("cast", []) or []
        if not isinstance(crew, list):
            crew = []
        if not isinstance(cast, list):
            cast = []

        directors = [
            person
            for person in crew
            if isinstance(person, dict)
            and (person.get("job") == "Director" or person.get("job") == "Series Director")
        ]
        for director in directors[:3]:
            director_id = director.get("id")
            director_name = director.get("name", "")
            director_node = TransientNode(
                id=f"tmdb:person:{director_id}",
                labels={"Person", "Director", "Entity"},
                properties={
                    "name": director_name,
                    "source": "tmdb",
                    "tmdb_id": director_id,
                },
            )
            self._add_node(graph, director_node, node_ids=node_ids)
            self._add_edge(
                graph,
                TransientEdge(
                    source=director_node.id,
                    target=tv_node.id,
                    relationship_type="DIRECTED",
                    properties={"source": "tmdb"},
                ),
                edge_keys=edge_keys,
            )

        for actor in cast[:5]:
            if not isinstance(actor, dict):
                continue
            actor_id = actor.get("id")
            actor_name = actor.get("name", "")
            character_name = actor.get("character", "")
            actor_node = TransientNode(
                id=f"tmdb:person:{actor_id}",
                labels={"Person", "Actor", "Entity"},
                properties={
                    "name": actor_name,
                    "character": character_name,
                    "source": "tmdb",
                    "tmdb_id": actor_id,
                },
            )
            self._add_node(graph, actor_node, node_ids=node_ids)
            self._add_edge(
                graph,
                TransientEdge(
                    source=actor_node.id,
                    target=tv_node.id,
                    relationship_type="ACTED_IN",
                    properties={"character": character_name, "source": "tmdb"},
                ),
                edge_keys=edge_keys,
            )

        genres = tv_data.get("genres", []) or []
        if not isinstance(genres, list):
            genres = []
        for genre in genres:
            if not isinstance(genre, dict):
                continue
            genre_id = genre.get("id")
            genre_name = genre.get("name", "")
            genre_node = TransientNode(
                id=f"tmdb:genre:{genre_id}",
                labels={"Genre", "Entity"},
                properties={"name": genre_name, "source": "tmdb"},
            )
            self._add_node(graph, genre_node, node_ids=node_ids)
            self._add_edge(
                graph,
                TransientEdge(
                    source=tv_node.id,
                    target=genre_node.id,
                    relationship_type="BELONGS_TO_GENRE",
                    properties={"source": "tmdb"},
                ),
                edge_keys=edge_keys,
            )

    def _add_person_to_graph(
        self,
        graph: TransientGraph,
        person_data: dict[str, Any],
        *,
        node_ids: set[str],
        edge_keys: set[tuple[str, str, str]],
    ) -> None:
        """Add a person and a small filmography slice to the graph."""
        person_id = person_data.get("id")
        person_name = person_data.get("name", "")
        person_bio = person_data.get("biography", "")
        dept = str(person_data.get("known_for_department") or "").strip()

        labels = {"Person", "Entity"}
        if dept:
            labels.add(dept)
            if dept.lower() == "directing":
                labels.add("Director")
            if dept.lower() == "acting":
                labels.add("Actor")

        person_node = TransientNode(
            id=f"tmdb:person:{person_id}",
            labels=labels,
            properties={
                "name": person_name,
                "description": person_bio,
                "birthday": person_data.get("birthday"),
                "place_of_birth": person_data.get("place_of_birth"),
                "known_for_department": dept,
                "source": "tmdb",
                "tmdb_id": person_id,
            },
        )
        self._add_node(graph, person_node, node_ids=node_ids)

        credits = person_data.get("combined_credits") or {}
        cast = credits.get("cast") or []
        crew = credits.get("crew") or []

        if not isinstance(cast, list):
            cast = []
        if not isinstance(crew, list):
            crew = []

        def _rank_credit(item: dict[str, Any]) -> tuple[float, float]:
            try:
                vote_count = float(item.get("vote_count") or 0.0)
                popularity = float(item.get("popularity") or 0.0)
            except Exception:
                vote_count, popularity = 0.0, 0.0
            return (vote_count, popularity)

        # Directed movies (crew).
        directed = [
            it
            for it in crew
            if isinstance(it, dict) and (it.get("job") == "Director" or it.get("department") == "Directing")
        ]
        directed.sort(key=_rank_credit, reverse=True)
        for it in directed[:10]:
            media_type = str(it.get("media_type") or "movie").strip().lower()
            item_id = it.get("id")
            if media_type == "tv":
                title = it.get("name") or it.get("original_name") or ""
                first_air_date = it.get("first_air_date") or ""
                target_node = TransientNode(
                    id=f"tmdb:tv:{item_id}",
                    labels={"TV", "Entity"},
                    properties={
                        "name": title,
                        "first_air_date": first_air_date,
                        "source": "tmdb",
                        "tmdb_id": item_id,
                    },
                )
            else:
                title = it.get("title") or it.get("original_title") or ""
                release_date = it.get("release_date") or ""
                target_node = TransientNode(
                    id=f"tmdb:movie:{item_id}",
                    labels={"Movie", "Entity"},
                    properties={
                        "name": title,
                        "release_date": release_date,
                        "source": "tmdb",
                        "tmdb_id": item_id,
                    },
                )
            self._add_node(graph, target_node, node_ids=node_ids)
            self._add_edge(
                graph,
                TransientEdge(
                    source=person_node.id,
                    target=target_node.id,
                    relationship_type="DIRECTED",
                    properties={"source": "tmdb"},
                ),
                edge_keys=edge_keys,
            )

        # Acted in movies (cast).
        acted = [it for it in cast if isinstance(it, dict)]
        acted.sort(key=_rank_credit, reverse=True)
        for it in acted[:10]:
            media_type = str(it.get("media_type") or "movie").strip().lower()
            item_id = it.get("id")
            character = it.get("character") or ""
            if media_type == "tv":
                title = it.get("name") or it.get("original_name") or ""
                first_air_date = it.get("first_air_date") or ""
                target_node = TransientNode(
                    id=f"tmdb:tv:{item_id}",
                    labels={"TV", "Entity"},
                    properties={
                        "name": title,
                        "first_air_date": first_air_date,
                        "source": "tmdb",
                        "tmdb_id": item_id,
                    },
                )
            else:
                title = it.get("title") or it.get("original_title") or ""
                release_date = it.get("release_date") or ""
                target_node = TransientNode(
                    id=f"tmdb:movie:{item_id}",
                    labels={"Movie", "Entity"},
                    properties={
                        "name": title,
                        "release_date": release_date,
                        "source": "tmdb",
                        "tmdb_id": item_id,
                    },
                )
            self._add_node(graph, target_node, node_ids=node_ids)
            self._add_edge(
                graph,
                TransientEdge(
                    source=person_node.id,
                    target=target_node.id,
                    relationship_type="ACTED_IN",
                    properties={"character": character, "source": "tmdb"},
                ),
                edge_keys=edge_keys,
            )
