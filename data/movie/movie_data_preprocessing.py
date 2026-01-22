#!/usr/bin/env python3
"""
电影数据预处理脚本（模块化版本）

入口文件仅负责 CLI 与流程编排；核心逻辑拆分到同目录的模块中：
- movielens_parser.py
- tmdb_client.py
- tmdb_cache.py
- enricher.py
- io_utils.py
"""

import argparse
import os
from collections import defaultdict
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from enricher import MovieDataEnricher
from io_utils import save_json
from movielens_parser import MovieLensParser
from tmdb_client import TMDBClient


def main():
    parser = argparse.ArgumentParser(
        description="电影数据预处理（MovieLens + TMDB，可离线降级）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整运行（推荐）
  python %(prog)s --source-dir SparrowRecSys-master/target/classes/webroot/sampledata

  # 自定义输出目录
  python %(prog)s --source-dir /path/to/data --output-dir files/movie_data

  # 调整速率限制（避免 TMDB 限流）
  python %(prog)s --source-dir /path/to/data --rate-limit 3.5
        """
    )

    parser.add_argument('--source-dir', type=str, required=True,
                       help='MovieLens 数据目录（包含 movies.csv, links.csv, ratings.csv）')
    parser.add_argument('--output-dir', type=str, default='files/movie_data',
                       help='输出目录（默认: files/movie_data）')
    parser.add_argument('--cache-dir', type=str, default='files/tmdb_cache',
                       help='TMDB 缓存目录（默认: files/tmdb_cache）')
    parser.add_argument('--rate-limit', type=float, default=4.0,
                       help='TMDB API 速率限制，单位: 请求/秒（默认: 4.0）')
    parser.add_argument('--skip-optional', action='store_true',
                       help='跳过可选 API 调用（recommendations, similar）以节省时间')
    parser.add_argument('--limit', type=int, default=0,
                       help='仅处理前 N 部电影（0 表示全部；用于快速烟囱测试）')

    args = parser.parse_args()

    load_dotenv()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    cache_dir = Path(args.cache_dir)

    # 验证源目录
    if not source_dir.exists():
        print(f"❌ 错误: 源数据目录不存在: {source_dir}")
        return 1

    required_files = ['movies.csv', 'links.csv', 'ratings.csv']
    for file in required_files:
        if not (source_dir / file).exists():
            print(f"❌ 错误: 缺少必需文件: {source_dir / file}")
            return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("🎬 电影数据预处理流程（完整修复版 v2.0）")
    print("=" * 80)
    print(f"源目录: {source_dir}")
    print(f"输出目录: {output_dir}")
    print(f"缓存目录: {cache_dir}")
    print(f"速率限制: {args.rate_limit} 请求/秒")

    # Step 1: 解析 MovieLens 数据
    print("\n" + "=" * 80)
    print("[1/4] 解析 MovieLens 数据")
    print("=" * 80)

    parser_ml = MovieLensParser(source_dir)

    movies_df = parser_ml.parse_movies()
    links_df = parser_ml.parse_links()
    ratings_stats = parser_ml.parse_ratings()

    print(f"\n✅ 电影数量: {len(movies_df)}")
    print(f"   - 有 TMDB ID: {links_df['tmdbId'].notna().sum()}")
    print(f"   - 无 TMDB ID: {links_df['tmdbId'].isna().sum()}")
    print(f"✅ 评分统计: {len(ratings_stats)} 部电影")

    # 合并 movies 和 links
    merged_df = movies_df.merge(links_df, on='movieId', how='left')
    if args.limit and args.limit > 0:
        merged_df = merged_df.head(args.limit).reset_index(drop=True)
        print(f"\n⚠️  limit 生效：仅处理前 {len(merged_df)} 部电影（用于快速验证流程）")

    # Step 2: 初始化 TMDB 客户端
    print("\n" + "=" * 80)
    print("[2/4] 初始化 TMDB API 客户端")
    print("=" * 80)

    tmdb_api_token = os.getenv("TMDB_API_TOKEN", "")
    tmdb_api_key = os.getenv("TMDB_API_KEY", "")

    if not tmdb_api_token and not tmdb_api_key:
        print("\n⚠️  警告: 未设置 TMDB_API_TOKEN 或 TMDB_API_KEY")
        print("   将仅使用 MovieLens 数据，跳过 TMDB 数据获取")
        print("   请在 .env 文件中设置 TMDB_API_TOKEN 以获取完整数据\n")
        tmdb_client = None
    else:
        # 读取代理配置
        proxies = {}
        http_proxy = os.getenv("HTTP_PROXY")
        https_proxy = os.getenv("HTTPS_PROXY")

        if http_proxy:
            proxies['http'] = http_proxy
        if https_proxy:
            proxies['https'] = https_proxy

        if proxies:
            print(f"\n✅ 使用代理: {proxies.get('https', proxies.get('http'))}")

        tmdb_client = TMDBClient(
            api_token=tmdb_api_token,
            api_key=tmdb_api_key,
            rate_limit=args.rate_limit,
            proxies=proxies if proxies else None
        )

        print(f"✅ TMDB 客户端初始化成功")
        print(f"   - 速率限制: {args.rate_limit} 请求/秒")
        print(f"   - 缓存目录: {cache_dir}\n")

    # Step 3: 增强电影数据
    print("=" * 80)
    print("[3/4] 增强电影数据（调用 TMDB API）")
    print("=" * 80)

    enricher = MovieDataEnricher(tmdb_client, cache_dir, skip_optional=args.skip_optional)
    enriched_movies = []

    for idx, row in tqdm(merged_df.iterrows(), total=len(merged_df), desc="处理电影"):
        movie_id = int(row['movieId'])
        rating_stat = ratings_stats.get(movie_id)
        enriched = enricher.enrich_movie(row, row, rating_stat)

        enriched_movies.append(enriched)

    print(f"\n✅ 处理完成: {len(enriched_movies)} 部电影")

    # Step 4: 保存结果
    print("\n" + "=" * 80)
    print("[4/4] 保存结果")
    print("=" * 80)

    # 4.1 保存电影数据
    movies_output = output_dir / "movies_enriched.json"
    save_json(enriched_movies, movies_output)
    print(f"\n✅ 电影数据: {movies_output}")
    print(f"   - 文件大小: {movies_output.stat().st_size / 1024 / 1024:.2f} MB")

    if tmdb_client:
        # 4.2 保存人物数据
        persons_output = output_dir / "persons.json"
        save_json(list(enricher.all_persons.values()), persons_output)
        print(f"\n✅ 人物数据: {persons_output}")
        print(f"   - 人数: {len(enricher.all_persons)}")

        # 统计人员类型
        person_types = defaultdict(int, enricher.summarize_person_types())
        print(f"   - 演员: {person_types.get('actor', 0)}")
        print(f"   - 导演: {person_types.get('director', 0)}")
        print(f"   - 既是演员又是导演: {person_types.get('both', 0)}")

        # 4.3 保存关键词
        keywords_output = output_dir / "keywords.json"
        save_json(list(enricher.all_keywords.values()), keywords_output)
        print(f"\n✅ 关键词数据: {keywords_output}")
        print(f"   - 关键词数: {len(enricher.all_keywords)}")

        # 4.4 保存制作公司
        companies_output = output_dir / "companies.json"
        save_json(list(enricher.all_companies.values()), companies_output)
        print(f"\n✅ 制作公司: {companies_output}")
        print(f"   - 公司数: {len(enricher.all_companies)}")

        # 4.5 保存国家
        countries_output = output_dir / "countries.json"
        save_json(list(enricher.all_countries.values()), countries_output)
        print(f"\n✅ 国家数据: {countries_output}")
        print(f"   - 国家数: {len(enricher.all_countries)}")

        # 4.6 保存语言
        languages_output = output_dir / "languages.json"
        save_json(list(enricher.all_languages.values()), languages_output)
        print(f"\n✅ 语言数据: {languages_output}")
        print(f"   - 语言数: {len(enricher.all_languages)}")

    # 最终统计
    print("\n" + "=" * 80)
    print("✅ 预处理完成!")
    print("=" * 80)

    # ✅ 修复统计逻辑
    tmdb_count = sum(1 for m in enriched_movies if m.get('data_source') == 'movielens+tmdb')
    movielens_only_count = len(enriched_movies) - tmdb_count

    print(f"\n📊 数据统计:")
    print(f"   - 总电影数: {len(enriched_movies)}")
    print(f"   - 包含 TMDB 数据: {tmdb_count} ({tmdb_count/len(enriched_movies)*100:.1f}%)")
    print(f"   - 仅 MovieLens 数据: {movielens_only_count} ({movielens_only_count/len(enriched_movies)*100:.1f}%)")

    if tmdb_client:
        print(f"\n📊 实体统计:")
        print(f"   - 人物: {len(enricher.all_persons)}")
        print(f"   - 关键词: {len(enricher.all_keywords)}")
        print(f"   - 制作公司: {len(enricher.all_companies)}")
        print(f"   - 国家: {len(enricher.all_countries)}")
        print(f"   - 语言: {len(enricher.all_languages)}")

    print(f"\n📁 输出文件位置: {output_dir}/")
    print(f"📁 TMDB 缓存位置: {cache_dir}/")

    return 0


if __name__ == "__main__":
    exit(main())
