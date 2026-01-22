#!/usr/bin/env python3
"""
小规模测试：处理前10部电影
"""

import os
import sys

# 在命令行参数中添加限制
sys.argv = [
    'movie_data_preprocessing.py',
    '--source-dir', 'SparrowRecSys-master/target/classes/webroot/sampledata',
    '--output-dir', 'files/test',
    '--cache-dir', 'files/tmdb_cache',
    '--rate-limit', '4'
]

# 修改脚本以只处理前10部电影
import movie_data_preprocessing

# Monkey patch 以限制处理数量
original_process = movie_data_preprocessing.main

def limited_main():
    # 临时修改以只处理前10部
    import movie_data_preprocessing as mdp

    # 运行原始 main，但在合并后截取
    print("=" * 80)
    print("小规模测试：仅处理前 10 部电影")
    print("=" * 80)

    original_process()

if __name__ == "__main__":
    limited_main()
