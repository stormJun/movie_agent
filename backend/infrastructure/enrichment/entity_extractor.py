"""
Entity extractor for detecting movie references in user queries.

This module provides regex-based extraction of movie titles from user queries,
supporting various Chinese and English quotation styles.
"""

from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extract simple movie/person entities from user queries using regex patterns.

    This is a lightweight fallback for enrichment when router LLM entity extraction
    is unavailable (e.g., heuristic routing path).
    """

    # Match book title marks 《》 (Chinese) - complete format
    BOOKTITLE_PATTERN = re.compile(r"《(.+?)》")

    # Match incomplete book title marks - only closing 》 (common in user input)
    # Uses escaped quotes to avoid syntax errors
    BOOKTITLE_INCOMPLETE_PATTERN = re.compile(r'([^《《\""",.!?;\s]{1,10})》')

    # Match quotation marks " " ' ' ' ' (Chinese and English)
    QUOTE_PATTERN = re.compile(r'["""](.+?)["""]')

    # Match "movie: xxx" or "film: xxx" patterns
    # Note: Using explicit character class to avoid syntax errors with Chinese punctuation
    MOVIE_KEYWORD_PATTERN = re.compile(
        r'(?:电影|影片|film|movie)(?:[:\s]+)([^《《""",.!?;]+)', re.IGNORECASE
    )

    # Very lightweight person-name patterns (best-effort).
    # Examples:
    #   "李安导演了哪些电影" => 李安
    #   "导演：李安" / "导演 李安" => 李安
    PERSON_BEFORE_ROLE_PATTERN = re.compile(
        r"([\u4e00-\u9fff]{2,6})\s*(?:导演|执导|主演|演员|编剧|监制)"
    )
    # Require a delimiter after the role keyword; avoid matching phrases like "导演了哪些电影".
    PERSON_AFTER_ROLE_PATTERN = re.compile(
        r"(?:导演|执导|主演|演员|编剧|监制)(?:\s*[:：]\s*|\s+)([\u4e00-\u9fff]{2,6})"
    )

    PERSON_BEFORE_ROLE_PATTERN_EN = re.compile(
        r"([A-Za-z][A-Za-z .'-]{1,40})\s+(?:director|actor|actress|writer|screenwriter)",
        re.IGNORECASE,
    )
    PERSON_AFTER_ROLE_PATTERN_EN = re.compile(
        r"(?:director|actor|actress|writer|screenwriter)(?:\s*[:：]\s*|\s+)([A-Za-z][A-Za-z .'-]{1,40})",
        re.IGNORECASE,
    )


    @classmethod
    def extract_movie_entities(cls, query: str, max_entities: int = 3) -> List[str]:
        """Extract movie titles from a user query.

        This method searches for movie titles using multiple regex patterns:
        1. Book title marks: 《title》
        2. Quotation marks: "title" or "title"
        3. Keyword patterns: "movie: title" or "film: title"

        Args:
            query: The user's query text
            max_entities: Maximum number of entities to extract (default: 3)

        Returns:
            A deduplicated list of movie titles in the order they were found.
        """
        if not query:
            return []

        entities = set()

        # 1. Match book title marks (highest priority) - complete format
        for match in cls.BOOKTITLE_PATTERN.finditer(query):
            entity = match.group(1).strip()
            if entity:
                entities.add(entity)

        # 1.5. Match incomplete book title marks - only closing 》
        # This handles cases where users type "电影名》" without the opening 《
        for match in cls.BOOKTITLE_INCOMPLETE_PATTERN.finditer(query):
            entity = match.group(1).strip()
            if entity:
                entities.add(entity)

        # 2. Match quotation marks
        for match in cls.QUOTE_PATTERN.finditer(query):
            entity = match.group(1).strip()
            if entity:
                entities.add(entity)

        # 3. Match keyword patterns
        for match in cls.MOVIE_KEYWORD_PATTERN.finditer(query):
            entity = match.group(1).strip()
            if entity:
                entities.add(entity)

        # Convert to list and limit to max_entities
        result = list(entities)[:max_entities]

        if result:
            logger.info(f"Extracted movie entities: {result}")

        return result

    @classmethod
    def extract_person_entities(cls, query: str, max_entities: int = 3) -> List[str]:
        """Extract likely person names from a user query (best-effort)."""
        if not query:
            return []

        entities: list[str] = []

        for pat in (
            cls.PERSON_BEFORE_ROLE_PATTERN,
            cls.PERSON_AFTER_ROLE_PATTERN,
            cls.PERSON_BEFORE_ROLE_PATTERN_EN,
            cls.PERSON_AFTER_ROLE_PATTERN_EN,
        ):
            for match in pat.finditer(query):
                name = (match.group(1) or "").strip()
                if not name:
                    continue
                if name not in entities:
                    entities.append(name)
                if len(entities) >= max_entities:
                    break
            if len(entities) >= max_entities:
                break

        if entities:
            logger.info(f"Extracted person entities: {entities}")

        return entities
