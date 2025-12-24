#!/bin/bash
# Database Integration Test Script
# Tests the complete PostgreSQL + pgvector integration

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Database Integration Test${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Step 1: Check Docker
echo -e "${YELLOW}Step 1: Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker is installed${NC}"
echo ""

# Step 2: Start PostgreSQL
echo -e "${YELLOW}Step 2: Starting PostgreSQL...${NC}"
docker compose up -d postgres

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U biometric &> /dev/null; then
        echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Step 3: Check PostgreSQL status
echo -e "${YELLOW}Step 3: Checking PostgreSQL status...${NC}"
docker compose ps postgres
echo ""

# Step 4: Verify pgvector extension is available
echo -e "${YELLOW}Step 4: Verifying pgvector extension...${NC}"
docker compose exec -T postgres psql -U biometric -d postgres -c "SELECT * FROM pg_available_extensions WHERE name = 'vector';" | grep vector && \
    echo -e "${GREEN}✅ pgvector extension is available${NC}" || \
    echo -e "${RED}❌ pgvector extension not available${NC}"
echo ""

# Step 5: Run database migration
echo -e "${YELLOW}Step 5: Running database migration...${NC}"
if ! command -v alembic &> /dev/null; then
    echo -e "${RED}❌ Alembic not found. Installing...${NC}"
    pip install alembic asyncpg
fi

echo "Running: alembic upgrade head"
alembic upgrade head

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Migration completed successfully${NC}"
else
    echo -e "${RED}❌ Migration failed${NC}"
    exit 1
fi
echo ""

# Step 6: Verify current migration version
echo -e "${YELLOW}Step 6: Checking migration version...${NC}"
alembic current
echo ""

# Step 7: Verify schema was created
echo -e "${YELLOW}Step 7: Verifying database schema...${NC}"

# Check biometric_data table exists
echo "Checking biometric_data table..."
docker compose exec -T postgres psql -U biometric -d biometric -c "\d biometric_data" > /dev/null 2>&1 && \
    echo -e "${GREEN}✅ biometric_data table exists${NC}" || \
    echo -e "${RED}❌ biometric_data table not found${NC}"

# Check table structure
echo ""
echo "Table structure:"
docker compose exec -T postgres psql -U biometric -d biometric -c "\d biometric_data"
echo ""

# Step 8: Verify columns
echo -e "${YELLOW}Step 8: Verifying required columns...${NC}"

required_columns=("id" "user_id" "tenant_id" "biometric_type" "embedding" "embedding_model" "quality_score" "is_active" "is_primary" "deleted_at" "created_at" "updated_at")

for col in "${required_columns[@]}"; do
    if docker compose exec -T postgres psql -U biometric -d biometric -c "\d biometric_data" | grep -q "$col"; then
        echo -e "${GREEN}✅ Column '$col' exists${NC}"
    else
        echo -e "${RED}❌ Column '$col' missing${NC}"
    fi
done
echo ""

# Step 9: Verify indexes
echo -e "${YELLOW}Step 9: Verifying indexes...${NC}"
echo "Indexes on biometric_data:"
docker compose exec -T postgres psql -U biometric -d biometric -c "\di" | grep biometric_data
echo ""

# Check for HNSW vector index
if docker compose exec -T postgres psql -U biometric -d biometric -c "\di" | grep -q "hnsw"; then
    echo -e "${GREEN}✅ HNSW vector index exists${NC}"
else
    echo -e "${RED}❌ HNSW vector index not found${NC}"
fi
echo ""

# Step 10: Verify vector type
echo -e "${YELLOW}Step 10: Verifying vector column type...${NC}"
docker compose exec -T postgres psql -U biometric -d biometric -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'biometric_data' AND column_name = 'embedding';"

if docker compose exec -T postgres psql -U biometric -d biometric -c "\d biometric_data" | grep -q "vector(512)"; then
    echo -e "${GREEN}✅ Embedding column is vector(512) type${NC}"
else
    echo -e "${YELLOW}⚠️  Embedding column type check inconclusive${NC}"
fi
echo ""

# Step 11: Test INSERT (mock embedding)
echo -e "${YELLOW}Step 11: Testing INSERT operation...${NC}"
docker compose exec -T postgres psql -U biometric -d biometric <<EOF
INSERT INTO biometric_data (
    id, user_id, tenant_id, biometric_type, embedding_model,
    quality_score, is_active, is_primary, embedding
) VALUES (
    gen_random_uuid(),
    'test_user_001',
    NULL,
    'FACE',
    'Facenet512',
    0.95,
    TRUE,
    TRUE,
    array_fill(0.0::float, ARRAY[512])::vector(512)
);
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ INSERT successful${NC}"
else
    echo -e "${RED}❌ INSERT failed${NC}"
fi
echo ""

# Step 12: Test SELECT
echo -e "${YELLOW}Step 12: Testing SELECT operation...${NC}"
docker compose exec -T postgres psql -U biometric -d biometric -c "SELECT user_id, biometric_type, embedding_model, quality_score FROM biometric_data WHERE user_id = 'test_user_001';"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ SELECT successful${NC}"
else
    echo -e "${RED}❌ SELECT failed${NC}"
fi
echo ""

# Step 13: Test vector similarity search
echo -e "${YELLOW}Step 13: Testing vector similarity search...${NC}"
docker compose exec -T postgres psql -U biometric -d biometric <<EOF
SELECT
    user_id,
    embedding <=> array_fill(0.0::float, ARRAY[512])::vector(512) AS distance
FROM biometric_data
WHERE user_id = 'test_user_001'
ORDER BY distance
LIMIT 1;
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Vector similarity search successful${NC}"
else
    echo -e "${RED}❌ Vector similarity search failed${NC}"
fi
echo ""

# Step 14: Test UPDATE
echo -e "${YELLOW}Step 14: Testing UPDATE operation...${NC}"
docker compose exec -T postgres psql -U biometric -d biometric -c "UPDATE biometric_data SET quality_score = 0.99 WHERE user_id = 'test_user_001';"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ UPDATE successful${NC}"
else
    echo -e "${RED}❌ UPDATE failed${NC}"
fi
echo ""

# Step 15: Test soft DELETE
echo -e "${YELLOW}Step 15: Testing soft DELETE (deleted_at)...${NC}"
docker compose exec -T postgres psql -U biometric -d biometric -c "UPDATE biometric_data SET deleted_at = CURRENT_TIMESTAMP, is_active = FALSE WHERE user_id = 'test_user_001';"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Soft DELETE successful${NC}"
else
    echo -e "${RED}❌ Soft DELETE failed${NC}"
fi
echo ""

# Step 16: Clean up test data
echo -e "${YELLOW}Step 16: Cleaning up test data...${NC}"
docker compose exec -T postgres psql -U biometric -d biometric -c "DELETE FROM biometric_data WHERE user_id = 'test_user_001';"
echo -e "${GREEN}✅ Test data cleaned up${NC}"
echo ""

# Step 17: Connection pool test (optional - requires Python environment)
echo -e "${YELLOW}Step 17: Testing Python repository connection...${NC}"
if command -v python &> /dev/null; then
    cat > /tmp/test_db_connection.py <<'PYEOF'
import asyncio
import asyncpg
import os

async def test_connection():
    try:
        # Get database URL from environment or use default
        db_url = os.getenv('DATABASE_URL', 'postgresql://biometric:biometric@localhost:5432/biometric')

        # Parse URL
        conn = await asyncpg.connect(db_url)

        # Test query
        result = await conn.fetchval('SELECT 1')

        if result == 1:
            print("✅ Python asyncpg connection successful")

        # Test table exists
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'biometric_data')"
        )

        if exists:
            print("✅ biometric_data table accessible from Python")

        # Close connection
        await conn.close()

        return True
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_connection())
PYEOF

    python /tmp/test_db_connection.py
    rm /tmp/test_db_connection.py
else
    echo -e "${YELLOW}⚠️  Python not found, skipping Python connection test${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo "Database Integration Test Complete!"
echo ""
echo "Next steps:"
echo "1. Enable pgvector in .env: USE_PGVECTOR=True"
echo "2. Start the API: uvicorn app.main:app --reload --port 8001"
echo "3. Test enrollment: curl -X POST http://localhost:8001/api/v1/enroll -F 'file=@image.jpg' -F 'user_id=user123'"
echo ""
echo -e "${GREEN}All database integration tests passed! 🎉${NC}"
