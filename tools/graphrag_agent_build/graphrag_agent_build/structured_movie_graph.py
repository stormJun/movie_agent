from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from rich.console import Console

from graphrag_agent.ports.neo4jdb import get_db_manager
from graphrag_agent.config.settings import STRUCTURED_DATA_DIR


@dataclass(frozen=True)
class MovieStructuredPaths:
    """电影结构化数据路径配置

    Attributes:
        data_dir: 数据目录路径
        movies_file: 电影数据文件路径 (movies_enriched.json)
        persons_file: 人物数据文件路径 (persons.json)
        keywords_file: 关键词数据文件路径 (keywords.json)
        companies_file: 公司数据文件路径 (companies.json)
        countries_file: 国家数据文件路径 (countries.json)
        languages_file: 语言数据文件路径 (languages.json)
    """
    data_dir: Path
    movies_file: Path
    persons_file: Path
    keywords_file: Path
    companies_file: Path
    countries_file: Path
    languages_file: Path


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    """从 JSON 文件加载数组数据

    Args:
        path: JSON 文件路径

    Returns:
        JSON 数组内容

    Raises:
        ValueError: 如果文件内容不是数组类型
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"期望 JSON 数组，但读取到: {path}")
    return data


def _batched(items: Sequence[Dict[str, Any]], batch_size: int) -> Iterable[List[Dict[str, Any]]]:
    """将序列分批处理

    Args:
        items: 要分批的数据序列
        batch_size: 每批大小

    Yields:
        每批数据的列表
    """
    for i in range(0, len(items), batch_size):
        yield list(items[i : i + batch_size])


class StructuredMovieGraphBuilder:
    """
    结构化模式（电影）Phase 2：导入领域图（:电影/:人物/:类型/:关键词...）
    + 生成 Canonical 层（__Document__/__Chunk__/__Entity__/MENTIONS/RELATED）。

    约定：
    - Canonical 实体 id 前缀使用 kb_prefix（默认 "movie"），避免与文档模式混用时冲突。
    - 默认不清空数据库；如需重建，使用 reset_* 开关仅删除 movie 前缀相关数据。
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        kb_prefix: str = "movie",
        domain_name: str = "电影知识图谱与推荐系统",
        batch_size: int = 500,
        reset_domain_graph: bool = False,
        reset_canonical_layer: bool = False,
    ):
        """初始化结构化电影图谱构建器

        Args:
            data_dir: 结构化数据目录路径,默认使用配置中的 STRUCTURED_DATA_DIR
            kb_prefix: 知识库 ID 前缀,用于区分不同知识库的实体 (默认 "movie")
            domain_name: 领域名称,用于 __Document__.domain 字段
            batch_size: 批量操作时的批次大小
            reset_domain_graph: 是否重置领域图(删除所有电影相关的领域节点)
            reset_canonical_layer: 是否重置 Canonical 层(删除所有 movie 前缀的标准化节点)
        """
        self.console = Console()
        self.db = get_db_manager()
        self.graph = self.db.get_graph()

        self.data_dir = Path(data_dir) if data_dir else Path(STRUCTURED_DATA_DIR)
        self.kb_prefix = kb_prefix
        self.domain_name = domain_name
        self.batch_size = batch_size
        self.reset_domain_graph = reset_domain_graph
        self.reset_canonical_layer = reset_canonical_layer

        self.paths = self._resolve_paths(self.data_dir)

    def _resolve_paths(self, data_dir: Path) -> MovieStructuredPaths:
        """
        兼容两种输出目录：
        - files/movie_data/movies_enriched.json
        - files/movies_enriched.json
        """
        candidates = [
            data_dir,
            data_dir / "movie_data",
        ]

        found_dir: Optional[Path] = None
        for cand in candidates:
            if (cand / "movies_enriched.json").exists():
                found_dir = cand
                break

        if not found_dir:
            raise FileNotFoundError(
                f"未找到 movies_enriched.json，已尝试: "
                f"{', '.join(str(c) for c in candidates)}"
            )

        return MovieStructuredPaths(
            data_dir=found_dir,
            movies_file=found_dir / "movies_enriched.json",
            persons_file=found_dir / "persons.json",
            keywords_file=found_dir / "keywords.json",
            companies_file=found_dir / "companies.json",
            countries_file=found_dir / "countries.json",
            languages_file=found_dir / "languages.json",
        )

    def process(self) -> None:
        """执行完整构建流程

        流程:
        1. 可选:重置领域图和/或 Canonical 层
        2. 创建数据库约束和索引
        3. 导入领域图数据(电影、人物、类型、关键词等)
        4. 生成 Canonical 层(__Document__/__Chunk__/__Entity__)
        """
        self.console.print("[bold cyan]结构化模式（电影）Phase 2: 领域图导入 + Canonical 层生成[/bold cyan]")
        if self.reset_domain_graph:
            self._reset_domain_graph()
        if self.reset_canonical_layer:
            self._reset_canonical_layer()

        self._create_constraints()
        self._import_domain_graph()
        self._generate_canonical_layer()

    # -------------------------
    # Reset / constraints
    # -------------------------

    def _reset_domain_graph(self) -> None:
        """重置领域图:删除所有电影相关的领域节点(电影、人物、类型、关键词等)"""
        self.console.print("[yellow]重置领域图（仅电影标签）...[/yellow]")
        self.graph.query(
            """
            MATCH (n)
            WHERE n:电影 OR n:人物 OR n:类型 OR n:关键词 OR n:公司 OR n:国家 OR n:语言
            DETACH DELETE n
            """
        )

    def _reset_canonical_layer(self) -> None:
        """重置 Canonical 层:仅删除以 kb_prefix 开头的标准化节点

        删除三类节点:
        1. __Entity__: 以 kb_prefix: 开头的实体
        2. __Chunk__: 以 kb_prefix: 开头的 chunk
        3. __Document__: fileName 以 kb_prefix: 开头的文档
        """
        self.console.print("[yellow]重置 Canonical 层（仅 movie 前缀）...[/yellow]")
        self.graph.query(
            """
            MATCH (e:__Entity__)
            WHERE e.id STARTS WITH $prefix
            DETACH DELETE e
            """,
            params={"prefix": f"{self.kb_prefix}:"},
        )
        self.graph.query(
            """
            MATCH (c:__Chunk__)
            WHERE c.id STARTS WITH $prefix OR c.fileName STARTS WITH $prefix
            DETACH DELETE c
            """,
            params={"prefix": f"{self.kb_prefix}:"},
        )
        self.graph.query(
            """
            MATCH (d:__Document__)
            WHERE d.fileName STARTS WITH $prefix
            DETACH DELETE d
            """,
            params={"prefix": f"{self.kb_prefix}:"},
        )

    def _create_constraints(self) -> None:
        """创建数据库约束和索引

        约束:保证领域节点的唯一性(movieId, personId, keywordId 等)
        索引:加速 Canonical 层节点的查询(fileName, id 等)
        """
        self.console.print("[cyan]创建约束与索引...[/cyan]")
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:电影) REQUIRE m.movieId IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:人物) REQUIRE p.personId IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (k:关键词) REQUIRE k.keywordId IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:类型) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:公司) REQUIRE c.companyId IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:国家) REQUIRE c.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:语言) REQUIRE l.code IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (d:__Document__) ON (d.fileName)",
            "CREATE INDEX IF NOT EXISTS FOR (c:__Chunk__) ON (c.id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:__Entity__) ON (e.id)",
        ]
        for q in queries:
            self.graph.query(q)

    # -------------------------
    # Domain import
    # -------------------------

    def _import_domain_graph(self) -> None:
        """导入领域图数据

        流程:
        1. 读取 JSON 数据文件(movies, persons, keywords)
        2. 导入各类节点(电影、人物、关键词)
        3. 导入关系(类型、演员、导演、关键词)

        注意:关系数据以 movies_enriched.json 为准,即使 persons.json/keywords.json 缺失
        """
        self.console.print(f"[cyan]读取结构化数据: {self.paths.data_dir}[/cyan]")
        movies = _load_json_list(self.paths.movies_file)
        persons: List[Dict[str, Any]] = []
        keywords: List[Dict[str, Any]] = []
        companies: List[Dict[str, Any]] = []
        countries: List[Dict[str, Any]] = []
        languages: List[Dict[str, Any]] = []

        if self.paths.persons_file.exists():
            persons = _load_json_list(self.paths.persons_file)
        if self.paths.keywords_file.exists():
            keywords = _load_json_list(self.paths.keywords_file)
        if self.paths.companies_file.exists():
            companies = _load_json_list(self.paths.companies_file)
        if self.paths.countries_file.exists():
            countries = _load_json_list(self.paths.countries_file)
        if self.paths.languages_file.exists():
            languages = _load_json_list(self.paths.languages_file)

        self.console.print(f"[blue]movies: {len(movies)}[/blue]")
        if persons:
            self.console.print(f"[blue]persons: {len(persons)}[/blue]")
        if keywords:
            self.console.print(f"[blue]keywords: {len(keywords)}[/blue]")
        if companies:
            self.console.print(f"[blue]companies: {len(companies)}[/blue]")
        if countries:
            self.console.print(f"[blue]countries: {len(countries)}[/blue]")
        if languages:
            self.console.print(f"[blue]languages: {len(languages)}[/blue]")

        self._import_movies(movies)
        if persons:
            self._import_persons(persons)
        if keywords:
            self._import_keywords(keywords)
        if companies:
            self._import_companies(companies)
        if countries:
            self._import_countries(countries)
        if languages:
            self._import_languages(languages)

        # 关系（优先以 movies_enriched.json 为准）
        self._import_movie_genres(movies)
        self._import_cast_and_crew(movies)
        self._import_movie_keywords(movies)
        self._import_movie_companies(movies)
        self._import_movie_countries(movies)
        self._import_movie_languages(movies)

    def _import_companies(self, companies: List[Dict[str, Any]]) -> None:
        """导入公司节点"""
        query = """
        UNWIND $rows AS row
        MERGE (c:公司 {companyId: row.companyId})
        SET c.name = row.name,
            c.origin_country = row.origin_country,
            c.movieIds = coalesce(row.movieIds, [])
        """
        for batch in _batched(companies, self.batch_size):
            self.graph.query(query, params={"rows": batch})

    def _import_countries(self, countries: List[Dict[str, Any]]) -> None:
        """导入国家节点"""
        query = """
        UNWIND $rows AS row
        MERGE (c:国家 {code: row.code})
        SET c.name = row.name,
            c.movieIds = coalesce(row.movieIds, [])
        """
        for batch in _batched(countries, self.batch_size):
            self.graph.query(query, params={"rows": batch})

    def _import_languages(self, languages: List[Dict[str, Any]]) -> None:
        """导入语言节点"""
        query = """
        UNWIND $rows AS row
        MERGE (l:语言 {code: row.code})
        SET l.name = row.name,
            l.movieIds = coalesce(row.movieIds, [])
        """
        for batch in _batched(languages, self.batch_size):
            self.graph.query(query, params={"rows": batch})

    def _import_movie_companies(self, movies: List[Dict[str, Any]]) -> None:
        """导入电影-公司关系（:制作公司）"""
        rows: List[Dict[str, Any]] = []
        for movie in movies:
            movie_id = movie.get("movieId")
            for comp in movie.get("production_companies", []) or []:
                company_id = comp.get("id")
                if company_id is None:
                    continue
                rows.append(
                    {
                        "movieId": movie_id,
                        "companyId": company_id,
                        "name": comp.get("name"),
                        "origin_country": comp.get("origin_country", ""),
                    }
                )

        if not rows:
            return

        ensure_query = """
        UNWIND $rows AS row
        MERGE (c:公司 {companyId: row.companyId})
        ON CREATE SET c.name = row.name,
                      c.origin_country = row.origin_country
        """
        rel_query = """
        UNWIND $rows AS row
        MATCH (m:电影 {movieId: row.movieId})
        MATCH (c:公司 {companyId: row.companyId})
        MERGE (m)-[:制作公司]->(c)
        """
        for batch in _batched(rows, self.batch_size):
            self.graph.query(ensure_query, params={"rows": batch})
            self.graph.query(rel_query, params={"rows": batch})

    def _import_movie_countries(self, movies: List[Dict[str, Any]]) -> None:
        """导入电影-国家关系（:制作国家）"""
        rows: List[Dict[str, Any]] = []
        for movie in movies:
            movie_id = movie.get("movieId")
            for c in movie.get("production_countries", []) or []:
                code = (c.get("code") or "").upper()
                if not code:
                    continue
                rows.append(
                    {
                        "movieId": movie_id,
                        "code": code,
                        "name": c.get("name"),
                    }
                )

        if not rows:
            return

        ensure_query = """
        UNWIND $rows AS row
        MERGE (c:国家 {code: row.code})
        ON CREATE SET c.name = row.name
        """
        rel_query = """
        UNWIND $rows AS row
        MATCH (m:电影 {movieId: row.movieId})
        MATCH (c:国家 {code: row.code})
        MERGE (m)-[:制作国家]->(c)
        """
        for batch in _batched(rows, self.batch_size):
            self.graph.query(ensure_query, params={"rows": batch})
            self.graph.query(rel_query, params={"rows": batch})

    def _import_movie_languages(self, movies: List[Dict[str, Any]]) -> None:
        """导入电影-语言关系（:使用语言）"""
        rows: List[Dict[str, Any]] = []
        for movie in movies:
            movie_id = movie.get("movieId")
            for l in movie.get("spoken_languages", []) or []:
                code = (l.get("code") or "").lower()
                if not code:
                    continue
                rows.append(
                    {
                        "movieId": movie_id,
                        "code": code,
                        "name": l.get("name"),
                    }
                )

        if not rows:
            return

        ensure_query = """
        UNWIND $rows AS row
        MERGE (l:语言 {code: row.code})
        ON CREATE SET l.name = row.name
        """
        rel_query = """
        UNWIND $rows AS row
        MATCH (m:电影 {movieId: row.movieId})
        MATCH (l:语言 {code: row.code})
        MERGE (m)-[:使用语言]->(l)
        """
        for batch in _batched(rows, self.batch_size):
            self.graph.query(ensure_query, params={"rows": batch})
            self.graph.query(rel_query, params={"rows": batch})

    def _import_movies(self, movies: List[Dict[str, Any]]) -> None:
        """导入电影节点

        使用 MERGE 避免重复,支持批量写入
        """
        query = """
        UNWIND $rows AS movie
        MERGE (m:电影 {movieId: movie.movieId})
        SET m.name = movie.name,
            m.year = movie.year,
            m.tmdbId = movie.tmdbId,
            m.imdbId = movie.imdbId,
            m.overview = movie.overview,
            m.description = movie.description,
            m.genres = coalesce(movie.genres, []),
            m.movielens_avg_rating = movie.movielens_avg_rating,
            m.movielens_rating_count = movie.movielens_rating_count,
            m.tmdb_vote_average = movie.tmdb_vote_average,
            m.tmdb_vote_count = movie.tmdb_vote_count,
            m.rank_score_0_10 = movie.rank_score_0_10,
            m.rank_score_source = movie.rank_score_source,
            m.rank_score_votes = movie.rank_score_votes,
            m.data_source = movie.data_source,
            m.created_at = movie.created_at
        """
        for batch in _batched(movies, self.batch_size):
            self.graph.query(query, params={"rows": batch})

    def _import_persons(self, persons: List[Dict[str, Any]]) -> None:
        """导入人物节点(演员/导演)

        包括姓名、人气度、头像路径等信息
        """
        query = """
        UNWIND $rows AS person
        MERGE (p:人物 {personId: person.personId})
        SET p.name = person.name,
            p.popularity = person.popularity,
            p.profile_path = person.profile_path,
            p.person_type = person.person_type,
            p.movieIds = coalesce(person.movieIds, [])
        """
        for batch in _batched(persons, self.batch_size):
            self.graph.query(query, params={"rows": batch})

    def _import_keywords(self, keywords: List[Dict[str, Any]]) -> None:
        """导入关键词节点

        用于电影的标签/关键词检索
        """
        query = """
        UNWIND $rows AS kw
        MERGE (k:关键词 {keywordId: kw.keywordId})
        SET k.name = kw.name,
            k.movieIds = coalesce(kw.movieIds, [])
        """
        for batch in _batched(keywords, self.batch_size):
            self.graph.query(query, params={"rows": batch})

    def _import_movie_genres(self, movies: List[Dict[str, Any]]) -> None:
        """导入电影-类型关系

        为每部电影创建 :属于类型 关系,类型节点自动创建
        """
        query = """
        UNWIND $rows AS movie
        MATCH (m:电影 {movieId: movie.movieId})
        WITH m, movie
        UNWIND coalesce(movie.genres, []) AS genre_name
        MERGE (t:类型 {name: genre_name})
        MERGE (m)-[:属于类型]->(t)
        """
        for batch in _batched(movies, self.batch_size):
            self.graph.query(query, params={"rows": batch})

    def _import_cast_and_crew(self, movies: List[Dict[str, Any]]) -> None:
        """导入演员和导演关系

        步骤:
        1. 从 movies 中提取 cast(演员) 和 crew(导演) 数据
        2. 确保人物节点存在(即使 persons.json 缺失也能补齐)
        3. 创建 :出演 和 :导演 关系

        注意:crew 中只导入导演(Director)职位
        """
        cast_rows: List[Dict[str, Any]] = []
        crew_rows: List[Dict[str, Any]] = []

        for movie in movies:
            movie_id = movie.get("movieId")
            for c in movie.get("cast", []) or []:
                cast_rows.append(
                    {
                        "movieId": movie_id,
                        "personId": c.get("personId"),
                        "name": c.get("name"),
                        "character": c.get("character"),
                        "order": c.get("order"),
                        "cast_id": c.get("cast_id"),
                        "popularity": c.get("popularity", 0),
                        "profile_path": c.get("profile_path", ""),
                    }
                )
            for c in movie.get("crew", []) or []:
                if c.get("job") != "Director":
                    continue
                crew_rows.append(
                    {
                        "movieId": movie_id,
                        "personId": c.get("personId"),
                        "name": c.get("name"),
                        "job": c.get("job"),
                        "popularity": c.get("popularity", 0),
                        "profile_path": c.get("profile_path", ""),
                    }
                )

        # 确保人物节点存在（即使 persons.json 缺失，也可从 cast/crew 补齐）
        ensure_person_query = """
        UNWIND $rows AS row
        MERGE (p:人物 {personId: row.personId})
        ON CREATE SET p.name = row.name,
                      p.popularity = row.popularity,
                      p.profile_path = row.profile_path
        """
        for batch in _batched(cast_rows + crew_rows, self.batch_size):
            self.graph.query(ensure_person_query, params={"rows": batch})

        cast_query = """
        UNWIND $rows AS row
        MATCH (m:电影 {movieId: row.movieId})
        MATCH (p:人物 {personId: row.personId})
        MERGE (p)-[r:出演]->(m)
        SET r.character = row.character,
            r.order = row.order,
            r.cast_id = row.cast_id
        """
        for batch in _batched(cast_rows, self.batch_size):
            self.graph.query(cast_query, params={"rows": batch})

        crew_query = """
        UNWIND $rows AS row
        MATCH (m:电影 {movieId: row.movieId})
        MATCH (p:人物 {personId: row.personId})
        MERGE (p)-[:导演]->(m)
        """
        for batch in _batched(crew_rows, self.batch_size):
            self.graph.query(crew_query, params={"rows": batch})

    def _import_movie_keywords(self, movies: List[Dict[str, Any]]) -> None:
        """导入电影-关键词关系

        步骤:
        1. 从 movies 中提取关键词数据
        2. 确保关键词节点存在(即使 keywords.json 缺失也能补齐)
        3. 创建 :包含关键词 关系
        """
        kw_rows: List[Dict[str, Any]] = []
        for movie in movies:
            movie_id = movie.get("movieId")
            for kw in movie.get("keywords", []) or []:
                kw_rows.append(
                    {
                        "movieId": movie_id,
                        "keywordId": kw.get("id"),
                        "name": kw.get("name"),
                    }
                )

        if not kw_rows:
            return

        ensure_kw_query = """
        UNWIND $rows AS row
        MERGE (k:关键词 {keywordId: row.keywordId})
        ON CREATE SET k.name = row.name
        """
        rel_query = """
        UNWIND $rows AS row
        MATCH (m:电影 {movieId: row.movieId})
        MATCH (k:关键词 {keywordId: row.keywordId})
        MERGE (m)-[:包含关键词]->(k)
        """
        for batch in _batched(kw_rows, self.batch_size):
            self.graph.query(ensure_kw_query, params={"rows": batch})
            self.graph.query(rel_query, params={"rows": batch})

    # -------------------------
    # Canonical layer
    # -------------------------

    def _generate_canonical_layer(self) -> None:
        """生成 Canonical 层节点和关系

        Canonical 层包括:
        1. __Entity__: 标准化实体(Movie/Person/Keyword/Genre)
        2. __Document__: 文档节点(每部电影一个文档)
        3. __Chunk__: 文本块节点(描述/类型/演员/导演/关键词)
        4. MENTIONS: Chunk -> Entity 的提及关系
        5. RELATED: Entity -> Entity 的关联关系

        目的:让结构化数据支持文档模式的检索和推理
        """
        self.console.print("[cyan]生成 Canonical 层（__Document__/__Chunk__/__Entity__）...[/cyan]")

        self._canonical_movies()
        self._canonical_persons()
        self._canonical_keywords()
        self._canonical_genres()
        self._canonical_companies()
        self._canonical_countries()
        self._canonical_languages()

        self._canonical_mentions()
        self._canonical_entity_relationships()

    def _canonical_movies(self) -> None:
        """为每部电影生成 Canonical 层节点

        创建:
        1. __Entity__: 电影实体(id=movie:Movie:movieId)
        2. __Document__: 文档节点(fileName=movie:movie:movieId)
        3. __Chunk__: 描述文本块(id=movie:movie:movieId:desc)
        4. PART_OF: Chunk -> Document
        5. MENTIONS: Chunk -> Entity
        """
        self.graph.query(
            """
            MATCH (m:电影)
            WITH m,
                 $kb AS kb,
                 $domain AS domain,
                 $uri AS uri,
                 coalesce(m.description, m.overview, m.name) AS text
            MERGE (e:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            SET e.name = m.name,
                e.type = "Movie",
                e.entity_type = "Movie",
                e.description = text
            MERGE (d:__Document__ {fileName: kb + ":movie:" + toString(m.movieId)})
            SET d.type = "structured",
                d.domain = domain,
                d.uri = uri
            MERGE (c:__Chunk__ {id: kb + ":movie:" + toString(m.movieId) + ":desc"})
            SET c.fileName = d.fileName,
                c.position = 1,
                c.text = text
            MERGE (c)-[:PART_OF]->(d)
            MERGE (c)-[:MENTIONS]->(e)
            """,
            params={
                "kb": self.kb_prefix,
                "domain": self.domain_name,
                "uri": str(self.paths.data_dir),
            },
        )

    def _canonical_persons(self) -> None:
        """为每个人物生成 Canonical 实体

        检测人物的角色(演员/导演),并在描述中标注
        """
        self.graph.query(
            """
            MATCH (p:人物)
            WITH p,
                 $kb AS kb,
                 (CASE WHEN (p)-[:出演]->() THEN 1 ELSE 0 END) AS has_actor,
                 (CASE WHEN (p)-[:导演]->() THEN 1 ELSE 0 END) AS has_director
            WITH p, kb,
                 (CASE
                    WHEN has_actor = 1 AND has_director = 1 THEN ["actor","director"]
                    WHEN has_actor = 1 THEN ["actor"]
                    WHEN has_director = 1 THEN ["director"]
                    ELSE []
                  END) AS roles
            MERGE (e:__Entity__ {id: kb + ":Person:" + toString(p.personId)})
            SET e.name = p.name,
                e.type = "Person",
                e.entity_type = "Person",
                e.description = p.name + (
                  CASE
                    WHEN size(roles) > 0 THEN " (" + reduce(s = "", r IN roles | s + CASE WHEN s = "" THEN r ELSE "," + r END) + ")"
                    ELSE ""
                  END
                )
            """,
            params={"kb": self.kb_prefix},
        )

    def _canonical_keywords(self) -> None:
        """为每个关键词生成 Canonical 实体"""
        self.graph.query(
            """
            MATCH (k:关键词)
            WITH k, $kb AS kb
            MERGE (e:__Entity__ {id: kb + ":Keyword:" + toString(k.keywordId)})
            SET e.name = k.name,
                e.type = "Keyword",
                e.entity_type = "Keyword",
                e.description = k.name
            """,
            params={"kb": self.kb_prefix},
        )

    def _canonical_genres(self) -> None:
        """为每个类型生成 Canonical 实体"""
        self.graph.query(
            """
            MATCH (t:类型)
            WITH t, $kb AS kb
            MERGE (e:__Entity__ {id: kb + ":Genre:" + t.name})
            SET e.name = t.name,
                e.type = "Genre",
                e.entity_type = "Genre",
                e.description = t.name
            """,
            params={"kb": self.kb_prefix},
        )

    def _canonical_companies(self) -> None:
        """为每个公司生成 Canonical 实体"""
        self.graph.query(
            """
            MATCH (c:公司)
            WITH c, $kb AS kb
            MERGE (e:__Entity__ {id: kb + ":Company:" + toString(c.companyId)})
            SET e.name = c.name,
                e.type = "Company",
                e.entity_type = "Company",
                e.description = coalesce(c.name, "")
            """,
            params={"kb": self.kb_prefix},
        )

    def _canonical_countries(self) -> None:
        """为每个国家生成 Canonical 实体"""
        self.graph.query(
            """
            MATCH (c:国家)
            WITH c, $kb AS kb
            MERGE (e:__Entity__ {id: kb + ":Country:" + c.code})
            SET e.name = c.name,
                e.type = "Country",
                e.entity_type = "Country",
                e.description = coalesce(c.name, c.code)
            """,
            params={"kb": self.kb_prefix},
        )

    def _canonical_languages(self) -> None:
        """为每个语言生成 Canonical 实体"""
        self.graph.query(
            """
            MATCH (l:语言)
            WITH l, $kb AS kb
            MERGE (e:__Entity__ {id: kb + ":Language:" + l.code})
            SET e.name = l.name,
                e.type = "Language",
                e.entity_type = "Language",
                e.description = coalesce(l.name, l.code)
            """,
            params={"kb": self.kb_prefix},
        )

    def _canonical_mentions(self) -> None:
        """生成 MENTIONS 关系,让结构化数据"有证据可回溯"

        为每部电影的关联信息创建额外的 Chunk:
        1. 类型 Chunk (position=2): 提及 Movie 和 Genre 实体
        2. 演员 Chunk (position=3): 提及 Movie 和 Person 实体
        3. 导演 Chunk (position=4): 提及 Movie 和 Person 实体
        4. 关键词 Chunk (position=5): 提及 Movie 和 Keyword 实体
        5. 公司 Chunk (position=6): 提及 Movie 和 Company 实体
        6. 国家 Chunk (position=7): 提及 Movie 和 Country 实体
        7. 语言 Chunk (position=8): 提及 Movie 和 Language 实体

        这样检索时可以通过 Chunk 找回原始数据来源
        """
        # genres mention
        self.graph.query(
            """
            MATCH (m:电影)-[:属于类型]->(t:类型)
            WITH m, collect(distinct t.name) AS genres, $kb AS kb
            WITH m, genres, kb,
                 kb + ":movie:" + toString(m.movieId) + ":genres" AS chunk_id,
                 "Movie: " + coalesce(m.name, "") +
                 (CASE WHEN m.year IS NOT NULL THEN " (" + toString(m.year) + ")" ELSE "" END) +
                 "\nGenres: " + reduce(s = "", g IN genres | s + CASE WHEN s = "" THEN g ELSE ", " + g END) +
                 "\n类型: " + reduce(s = "", g IN genres | s + CASE WHEN s = "" THEN g ELSE ", " + g END) AS text
            MERGE (c:__Chunk__ {id: chunk_id})
            SET c.fileName = kb + ":movie:" + toString(m.movieId),
                c.position = 2,
                c.text = text
            WITH m, genres, c, kb
            MATCH (d:__Document__ {fileName: kb + ":movie:" + toString(m.movieId)})
            MERGE (c)-[:PART_OF]->(d)
            WITH m, c, kb
            MATCH (e:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (c)-[:MENTIONS]->(e)
            WITH m, c, kb
            MATCH (m)-[:属于类型]->(t:类型)
            MATCH (ge:__Entity__ {id: kb + ":Genre:" + t.name})
            MERGE (c)-[:MENTIONS]->(ge)
            """,
            params={"kb": self.kb_prefix},
        )

        # company mention
        self.graph.query(
            """
            MATCH (m:电影)-[:制作公司]->(c:公司)
            WITH m, collect(distinct c.name)[0..30] AS names, $kb AS kb
            WITH m, names, kb,
                 kb + ":movie:" + toString(m.movieId) + ":companies" AS chunk_id,
                 (CASE
                    WHEN size(names) = 0 THEN null
                    ELSE
                      "Movie: " + coalesce(m.name, "") +
                      (CASE WHEN m.year IS NOT NULL THEN " (" + toString(m.year) + ")" ELSE "" END) +
                      "\nCompanies: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END) +
                      "\n制作公司: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END)
                  END) AS text
            WHERE text IS NOT NULL
            MERGE (cch:__Chunk__ {id: chunk_id})
            SET cch.fileName = kb + ":movie:" + toString(m.movieId),
                cch.position = 6,
                cch.text = text
            WITH m, cch, kb
            MATCH (d:__Document__ {fileName: kb + ":movie:" + toString(m.movieId)})
            MERGE (cch)-[:PART_OF]->(d)
            WITH m, cch, kb
            MATCH (e:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (cch)-[:MENTIONS]->(e)
            WITH m, cch, kb
            MATCH (m)-[:制作公司]->(c:公司)
            MATCH (ce:__Entity__ {id: kb + ":Company:" + toString(c.companyId)})
            MERGE (cch)-[:MENTIONS]->(ce)
            """,
            params={"kb": self.kb_prefix},
        )

        # country mention
        self.graph.query(
            """
            MATCH (m:电影)-[:制作国家]->(c:国家)
            WITH m, collect(distinct c.name)[0..20] AS names, $kb AS kb
            WITH m, names, kb,
                 kb + ":movie:" + toString(m.movieId) + ":countries" AS chunk_id,
                 (CASE
                    WHEN size(names) = 0 THEN null
                    ELSE
                      "Movie: " + coalesce(m.name, "") +
                      (CASE WHEN m.year IS NOT NULL THEN " (" + toString(m.year) + ")" ELSE "" END) +
                      "\nCountries: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END) +
                      "\n制作国家: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END)
                  END) AS text
            WHERE text IS NOT NULL
            MERGE (cch:__Chunk__ {id: chunk_id})
            SET cch.fileName = kb + ":movie:" + toString(m.movieId),
                cch.position = 7,
                cch.text = text
            WITH m, cch, kb
            MATCH (d:__Document__ {fileName: kb + ":movie:" + toString(m.movieId)})
            MERGE (cch)-[:PART_OF]->(d)
            WITH m, cch, kb
            MATCH (e:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (cch)-[:MENTIONS]->(e)
            WITH m, cch, kb
            MATCH (m)-[:制作国家]->(c:国家)
            MATCH (ce:__Entity__ {id: kb + ":Country:" + c.code})
            MERGE (cch)-[:MENTIONS]->(ce)
            """,
            params={"kb": self.kb_prefix},
        )

        # language mention
        self.graph.query(
            """
            MATCH (m:电影)-[:使用语言]->(l:语言)
            WITH m, collect(distinct l.name)[0..20] AS names, $kb AS kb
            WITH m, names, kb,
                 kb + ":movie:" + toString(m.movieId) + ":languages" AS chunk_id,
                 (CASE
                    WHEN size(names) = 0 THEN null
                    ELSE
                      "Movie: " + coalesce(m.name, "") +
                      (CASE WHEN m.year IS NOT NULL THEN " (" + toString(m.year) + ")" ELSE "" END) +
                      "\nLanguages: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END) +
                      "\n语言: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END)
                  END) AS text
            WHERE text IS NOT NULL
            MERGE (cch:__Chunk__ {id: chunk_id})
            SET cch.fileName = kb + ":movie:" + toString(m.movieId),
                cch.position = 8,
                cch.text = text
            WITH m, cch, kb
            MATCH (d:__Document__ {fileName: kb + ":movie:" + toString(m.movieId)})
            MERGE (cch)-[:PART_OF]->(d)
            WITH m, cch, kb
            MATCH (e:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (cch)-[:MENTIONS]->(e)
            WITH m, cch, kb
            MATCH (m)-[:使用语言]->(l:语言)
            MATCH (le:__Entity__ {id: kb + ":Language:" + l.code})
            MERGE (cch)-[:MENTIONS]->(le)
            """,
            params={"kb": self.kb_prefix},
        )

        # cast mention
        self.graph.query(
            """
            MATCH (p:人物)-[r:出演]->(m:电影)
            WITH m, collect(distinct p.name)[0..20] AS names, $kb AS kb
            WITH m, names, kb,
                 kb + ":movie:" + toString(m.movieId) + ":cast" AS chunk_id,
                 (CASE
                    WHEN size(names) = 0 THEN null
                    ELSE
                      "Movie: " + coalesce(m.name, "") +
                      (CASE WHEN m.year IS NOT NULL THEN " (" + toString(m.year) + ")" ELSE "" END) +
                      "\nCast: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END) +
                      "\n主演: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END)
                  END) AS text
            WHERE text IS NOT NULL
            MERGE (c:__Chunk__ {id: chunk_id})
            SET c.fileName = kb + ":movie:" + toString(m.movieId),
                c.position = 3,
                c.text = text
            WITH m, c, kb
            MATCH (d:__Document__ {fileName: kb + ":movie:" + toString(m.movieId)})
            MERGE (c)-[:PART_OF]->(d)
            WITH m, c, kb
            MATCH (e:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (c)-[:MENTIONS]->(e)
            WITH m, c, kb
            MATCH (p:人物)-[:出演]->(m)
            MATCH (pe:__Entity__ {id: kb + ":Person:" + toString(p.personId)})
            MERGE (c)-[:MENTIONS]->(pe)
            """,
            params={"kb": self.kb_prefix},
        )

        # director mention
        self.graph.query(
            """
            MATCH (p:人物)-[:导演]->(m:电影)
            WITH m, collect(distinct p.name) AS names, $kb AS kb
            WITH m, names, kb,
                 kb + ":movie:" + toString(m.movieId) + ":director" AS chunk_id,
                 (CASE
                    WHEN size(names) = 0 THEN null
                    ELSE
                      "Movie: " + coalesce(m.name, "") +
                      (CASE WHEN m.year IS NOT NULL THEN " (" + toString(m.year) + ")" ELSE "" END) +
                      "\nDirector: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END) +
                      "\n导演: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END)
                  END) AS text
            WHERE text IS NOT NULL
            MERGE (c:__Chunk__ {id: chunk_id})
            SET c.fileName = kb + ":movie:" + toString(m.movieId),
                c.position = 4,
                c.text = text
            WITH m, c, kb
            MATCH (d:__Document__ {fileName: kb + ":movie:" + toString(m.movieId)})
            MERGE (c)-[:PART_OF]->(d)
            WITH m, c, kb
            MATCH (e:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (c)-[:MENTIONS]->(e)
            WITH m, c, kb
            MATCH (p:人物)-[:导演]->(m)
            MATCH (pe:__Entity__ {id: kb + ":Person:" + toString(p.personId)})
            MERGE (c)-[:MENTIONS]->(pe)
            """,
            params={"kb": self.kb_prefix},
        )

        # keyword mention
        self.graph.query(
            """
            MATCH (m:电影)-[:包含关键词]->(k:关键词)
            WITH m, collect(distinct k.name)[0..30] AS names, $kb AS kb
            WITH m, names, kb,
                 kb + ":movie:" + toString(m.movieId) + ":keywords" AS chunk_id,
                 (CASE
                    WHEN size(names) = 0 THEN null
                    ELSE
                      "Movie: " + coalesce(m.name, "") +
                      (CASE WHEN m.year IS NOT NULL THEN " (" + toString(m.year) + ")" ELSE "" END) +
                      "\nKeywords: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END) +
                      "\n关键词: " + reduce(s = "", n IN names | s + CASE WHEN s = "" THEN n ELSE ", " + n END)
                  END) AS text
            WHERE text IS NOT NULL
            MERGE (c:__Chunk__ {id: chunk_id})
            SET c.fileName = kb + ":movie:" + toString(m.movieId),
                c.position = 5,
                c.text = text
            WITH m, c, kb
            MATCH (d:__Document__ {fileName: kb + ":movie:" + toString(m.movieId)})
            MERGE (c)-[:PART_OF]->(d)
            WITH m, c, kb
            MATCH (e:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (c)-[:MENTIONS]->(e)
            WITH m, c, kb
            MATCH (m)-[:包含关键词]->(k:关键词)
            MATCH (ke:__Entity__ {id: kb + ":Keyword:" + toString(k.keywordId)})
            MERGE (c)-[:MENTIONS]->(ke)
            """,
            params={"kb": self.kb_prefix},
        )

    def _canonical_entity_relationships(self) -> None:
        """生成 __Entity__ 之间的 RELATED 关系

        将领域图的关系映射到 Canonical 层:
        1. Movie -[:RELATED]-> Genre (描述: "属于类型")
        2. Person -[:RELATED]-> Movie (描述: "出演")
        3. Person -[:RELATED]-> Movie (描述: "导演")
        4. Movie -[:RELATED]-> Keyword (描述: "包含关键词")
        5. Movie -[:RELATED]-> Company (描述: "制作公司")
        6. Movie -[:RELATED]-> Country (描述: "制作国家")
        7. Movie -[:RELATED]-> Language (描述: "使用语言")

        目的:让社区检测和关系检索能工作,无需 LLM 抽取
        """
        self.graph.query(
            """
            MATCH (m:电影)-[:属于类型]->(t:类型)
            WITH m, t, $kb AS kb
            MATCH (me:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MATCH (ge:__Entity__ {id: kb + ":Genre:" + t.name})
            MERGE (me)-[r:RELATED]->(ge)
            ON CREATE SET r.description = "属于类型", r.weight = 1.0
            """,
            params={"kb": self.kb_prefix},
        )

        self.graph.query(
            """
            MATCH (m:电影)-[:制作公司]->(c:公司)
            WITH m, c, $kb AS kb
            MATCH (me:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MATCH (ce:__Entity__ {id: kb + ":Company:" + toString(c.companyId)})
            MERGE (me)-[r:RELATED]->(ce)
            ON CREATE SET r.description = "制作公司", r.weight = 1.0
            """,
            params={"kb": self.kb_prefix},
        )

        self.graph.query(
            """
            MATCH (m:电影)-[:制作国家]->(c:国家)
            WITH m, c, $kb AS kb
            MATCH (me:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MATCH (ce:__Entity__ {id: kb + ":Country:" + c.code})
            MERGE (me)-[r:RELATED]->(ce)
            ON CREATE SET r.description = "制作国家", r.weight = 1.0
            """,
            params={"kb": self.kb_prefix},
        )

        self.graph.query(
            """
            MATCH (m:电影)-[:使用语言]->(l:语言)
            WITH m, l, $kb AS kb
            MATCH (me:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MATCH (le:__Entity__ {id: kb + ":Language:" + l.code})
            MERGE (me)-[r:RELATED]->(le)
            ON CREATE SET r.description = "使用语言", r.weight = 1.0
            """,
            params={"kb": self.kb_prefix},
        )

        self.graph.query(
            """
            MATCH (p:人物)-[:出演]->(m:电影)
            WITH p, m, $kb AS kb
            MATCH (pe:__Entity__ {id: kb + ":Person:" + toString(p.personId)})
            MATCH (me:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (pe)-[r:RELATED]->(me)
            ON CREATE SET r.description = "出演", r.weight = 1.0
            """,
            params={"kb": self.kb_prefix},
        )

        self.graph.query(
            """
            MATCH (p:人物)-[:导演]->(m:电影)
            WITH p, m, $kb AS kb
            MATCH (pe:__Entity__ {id: kb + ":Person:" + toString(p.personId)})
            MATCH (me:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MERGE (pe)-[r:RELATED]->(me)
            ON CREATE SET r.description = "导演", r.weight = 1.0
            """,
            params={"kb": self.kb_prefix},
        )

        self.graph.query(
            """
            MATCH (m:电影)-[:包含关键词]->(k:关键词)
            WITH m, k, $kb AS kb
            MATCH (me:__Entity__ {id: kb + ":Movie:" + toString(m.movieId)})
            MATCH (ke:__Entity__ {id: kb + ":Keyword:" + toString(k.keywordId)})
            MERGE (me)-[r:RELATED]->(ke)
            ON CREATE SET r.description = "包含关键词", r.weight = 1.0
            """,
            params={"kb": self.kb_prefix},
        )
