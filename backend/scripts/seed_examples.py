import asyncio
import os
import sys
from pathlib import Path

# Add backend root to sys.path to allow imports
backend_root = Path(__file__).parent.parent
sys.path.append(str(backend_root))

from config.database import get_postgres_dsn
import asyncpg

EXAMPLES = [
    "推荐几部90年代的高分科幻电影",
    "Inception的导演是谁？",
    "黑客帝国的主要类型是什么？",
    "找几部类似星际穿越的电影"
]

async def seed():
    dsn = get_postgres_dsn()
    if not dsn:
        print("Error: No POSTGRES_DSN found.")
        return

    print(f"Connecting to DB...")
    conn = await asyncpg.connect(dsn)
    try:
        # Check if table exists
        print("Ensuring table exists...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS example_questions (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                content text NOT NULL,
                is_active boolean DEFAULT true,
                created_at timestamptz DEFAULT now()
            );
        """)

        # Clear existing
        print("Clearing existing examples...")
        await conn.execute("DELETE FROM example_questions;")

        # Insert new
        print("Inserting new examples...")
        for q in EXAMPLES:
            await conn.execute(
                "INSERT INTO example_questions (content, is_active) VALUES ($1, $2)",
                q, True
            )
        
        print(f"Successfully inserted {len(EXAMPLES)} examples.")

    except Exception as e:
        print(f"Error seeding examples: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed())
