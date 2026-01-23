import asyncio
import sys
from pathlib import Path

# Add backend root to sys.path
backend_root = Path(__file__).parent.parent
sys.path.append(str(backend_root))

from infrastructure.persistence.postgres.example_store import PostgresExampleStore
from config.database import get_postgres_dsn

async def verify():
    dsn = get_postgres_dsn()
    if not dsn:
        print("Error: No POSTGRES_DSN found.")
        return

    print(f"Connecting to DB with DSN: {dsn}")
    store = PostgresExampleStore(dsn=dsn)
    try:
        examples = await store.list_examples()
        print(f"Found {len(examples)} examples:")
        for ex in examples:
            print(f"- {ex}")
            
        if len(examples) > 0:
            print("VERIFICATION SUCCESS: Examples found in DB.")
        else:
            print("VERIFICATION FAILED: No examples found.")
            
    except Exception as e:
        print(f"Error checking examples: {e}")
    finally:
        await store.close()

if __name__ == "__main__":
    asyncio.run(verify())
