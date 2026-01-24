import asyncio
import os
import sys
import asyncpg
from dotenv import load_dotenv

# Add backend to path so we can reuse config logic if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

# Load env from .env file in root
load_dotenv(override=True)

async def main():
    # Construct DSN manually or from env
    # Using localhost for host since we run on host
    host = "localhost"
    port = os.getenv("POSTGRES_PORT", "5433") # Default to 5433 as per docker-compose
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "graphrag_chat")
    
    dsn = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    print(f"Connecting to {dsn}...")

    try:
        conn = await asyncpg.connect(dsn)
        print("Connected.")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    try:
        # Fetch negative feedback
        rows = await conn.fetch("""
            SELECT id, message_id, query, is_positive, thread_id, agent_type, created_at
            FROM feedback 
            WHERE is_positive = false
            ORDER BY created_at DESC
        """)

        print(f"\nFound {len(rows)} negative feedback entries.\n")

        for r in rows:
            print("-" * 60)
            print(f"Feedback ID: {r['id']}")
            print(f"Time: {r['created_at']}")
            print(f"Agent: {r['agent_type']}")
            print(f"User Query (from feedback): {r['query']}")
            
            thread_id = r['thread_id']
            # Find conversation
            conv = await conn.fetchrow("SELECT id FROM conversations WHERE session_id = $1", thread_id)
            if not conv:
                print(f"  [WARN] Conversation not found for session_id: {thread_id}")
                continue
                
            conv_id = conv['id']
            msgs = await conn.fetch("SELECT role, content FROM messages WHERE conversation_id = $1 ORDER BY created_at", conv_id)
            
            # Simple heuristic: find the user message that matches the feedback query
            # Then show the assistant response immediately following it.
            
            target_idx = -1
            for i, m in enumerate(msgs):
                # Check approximate match or exact match
                if m['role'] == 'user':
                    if r['query'] and r['query'] in m['content']:
                        target_idx = i
                        break
                    # Or if query is very long/short, maybe just check if it's the latest one before feedback creation? 
                    # But feedback creation might be later.
                    
            if target_idx != -1:
                # Show context (previous 2 messages)
                start_ctx = max(0, target_idx - 2)
                if start_ctx < target_idx:
                    print(f"  > [Context] Previous Messages:")
                    for k in range(start_ctx, target_idx):
                        print(f"    - [{msgs[k]['role']}]: {msgs[k]['content'][:100]}...")

                print(f"  > Matched User Message in History: {msgs[target_idx]['content'][:100]}...")
                if target_idx + 1 < len(msgs) and msgs[target_idx+1]['role'] == 'assistant':
                    resp = msgs[target_idx+1]['content']
                    print(f"  > Assistant Response:\n{resp[:500]} ... [truncated]")
                else:
                    print("  > [WARN] No assistant response found immediately after.")
            else:
                 print("  > [WARN] Could not find matching user query in history.")
                 # Fallback: Print last interaction
                 if msgs:
                     last_msg = msgs[-1]
                     print(f"  > Last Message in Thread ({last_msg['role']}): {last_msg['content'][:200]}...")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
