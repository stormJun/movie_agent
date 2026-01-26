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
        graph = TransientGraph()

        for movie_data in movie_data_list:
            self._add_movie_to_graph(graph, movie_data)

        logger.info(
            f"Built TransientGraph: {len(graph.nodes)} nodes, " f"{len(graph.edges)} edges"
        )

        return graph

    def _add_movie_to_graph(self, graph: TransientGraph, movie_data: dict[str, Any]) -> None:
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
        graph.nodes.append(movie_node)

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
            graph.nodes.append(director_node)

            # Director -> Movie edge
            graph.edges.append(
                TransientEdge(
                    source=director_node.id,
                    target=movie_node.id,
                    relationship_type="DIRECTED",
                    properties={"source": "tmdb"},
                )
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
            graph.nodes.append(actor_node)

            # Actor -> Movie edge
            graph.edges.append(
                TransientEdge(
                    source=actor_node.id,
                    target=movie_node.id,
                    relationship_type="ACTED_IN",
                    properties={"character": character_name, "source": "tmdb"},
                )
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
            graph.nodes.append(genre_node)

            # Movie -> Genre edge
            graph.edges.append(
                TransientEdge(
                    source=movie_node.id,
                    target=genre_node.id,
                    relationship_type="BELONGS_TO_GENRE",
                    properties={"source": "tmdb"},
                )
            )
