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
    """Extract movie entities from user queries using regex patterns."""

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
