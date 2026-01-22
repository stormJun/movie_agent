# 电影数据预处理（MovieLens + TMDB）

本目录用于生成电影推荐知识图谱的 Phase 1 数据文件（JSON），供后续建图导入使用。

## 📁 目录结构

```
data/movie/
├── README.md
├── movie_data_preprocessing.py    # 完整预处理脚本（MovieLens + TMDB，可离线降级）
└── quickstart.sh                  # 一键运行预处理（含目录检查与交互确认）
```

## 🚀 快速开始

```bash
bash data/movie/quickstart.sh
```

## 🧩 直接运行脚本

```bash
python3 data/movie/movie_data_preprocessing.py \
  --source-dir SparrowRecSys-master/target/classes/webroot/sampledata \
  --output-dir files/movie_data \
  --cache-dir files/tmdb_cache \
  --rate-limit 3.5
```

可选参数：
- `--skip-optional`：跳过 TMDB 的 `recommendations` / `similar` 两个可选端点，减少请求量

## 📦 输出文件

当配置了 `TMDB_API_TOKEN` 或 `TMDB_API_KEY` 时（MovieLens + TMDB）：
- `files/movie_data/movies_enriched.json`
- `files/movie_data/persons.json`
- `files/movie_data/keywords.json`
- `files/movie_data/companies.json`
- `files/movie_data/countries.json`
- `files/movie_data/languages.json`

当未配置 TMDB 凭证时（仅 MovieLens，脚本会提示并自动降级）：
- `files/movie_data/movies_enriched.json`

TMDB 响应缓存：
- `files/tmdb_cache/movie_{tmdbId}.json`

## ⚙️ 环境变量（.env）

```env
# 推荐：Bearer Token
TMDB_API_TOKEN=<YOUR_TMDB_BEARER_TOKEN>

# 可选：API Key（脚本支持二选一）
TMDB_API_KEY=<YOUR_TMDB_API_KEY>

# 可选：网络受限/直连超时
HTTP_PROXY=http://localhost:10808
HTTPS_PROXY=http://localhost:10808
```

## 📚 相关文档

- 设计文档：`docs/06-应用案例/电影推荐知识图谱设计文档.md`
- 前端交互设计：`docs/06-应用案例/电影推荐知识图谱前端交互设计.md`
