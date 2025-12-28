#!/usr/bin/env python3
"""
Database Initialization Script for Cloud Run Job
This script enables the pgvector extension and creates required tables.
"""

import os
import sys

def main():
    # Use synchronous psycopg2 for simple one-time operations
    try:
        import psycopg2
    except ImportError:
        print("Installing psycopg2-binary...")
        os.system("pip install psycopg2-binary")
        import psycopg2

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print(f"Connecting to database...")

    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cursor = conn.cursor()

        print("1. Creating pgvector extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector CASCADE;")

        print("2. Verifying extension...")
        cursor.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
        result = cursor.fetchone()
        if result:
            print(f"   pgvector extension installed: {result[0]} v{result[1]}")
        else:
            print("   WARNING: pgvector extension not found!")

        print("3. Creating face_embeddings table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id SERIAL PRIMARY KEY,
                external_id VARCHAR(255) UNIQUE NOT NULL,
                embedding vector(128) NOT NULL,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        print("4. Creating vector index...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS face_embeddings_vector_idx
                ON face_embeddings
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
        """)

        print("5. Creating external_id index...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS face_embeddings_external_id_idx
                ON face_embeddings (external_id);
        """)

        print("6. Verification...")
        cursor.execute("""
            SELECT
                'pgvector' as component,
                CASE WHEN EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
                     THEN 'OK' ELSE 'MISSING' END as status
            UNION ALL
            SELECT
                'face_embeddings table',
                CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'face_embeddings')
                     THEN 'OK' ELSE 'MISSING' END
            UNION ALL
            SELECT
                'vector index',
                CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'face_embeddings_vector_idx')
                     THEN 'OK' ELSE 'MISSING' END;
        """)

        print("\n   Status Check:")
        for row in cursor.fetchall():
            print(f"   - {row[0]}: {row[1]}")

        cursor.execute("SELECT COUNT(*) FROM face_embeddings;")
        count = cursor.fetchone()[0]
        print(f"\n   Current enrollments: {count}")

        cursor.close()
        conn.close()

        print("\n✅ Database initialization completed successfully!")
        return 0

    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
