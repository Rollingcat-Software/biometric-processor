#!/bin/bash
# Port Verification Script
# Checks that all files use standardized ports

echo "🔍 Port Standardization Verification"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
errors=0
warnings=0

# Standard ports
API_PORT=8001
UI_PORT=3000
POSTGRES_PORT=5432
REDIS_PORT=6379
PROMETHEUS_PORT=9090

echo "📋 Standard Ports:"
echo "  - API: ${API_PORT}"
echo "  - UI: ${UI_PORT}"
echo "  - PostgreSQL: ${POSTGRES_PORT}"
echo "  - Redis: ${REDIS_PORT}"
echo "  - Prometheus: ${PROMETHEUS_PORT}"
echo ""

# Check for deprecated port 8000
echo "🚫 Checking for deprecated port 8000..."
deprecated_8000=$(grep -r ":8000\|port.*8000\|PORT.*8000" . \
  --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include=".env*" \
  --exclude-dir={.git,node_modules,.next,venv,__pycache__} \
  --exclude="PORT_STANDARDS.md" --exclude="verify_ports.sh" 2>/dev/null | wc -l)

if [ "$deprecated_8000" -gt 0 ]; then
  echo -e "${RED}❌ Found $deprecated_8000 references to deprecated port 8000${NC}"
  grep -rn ":8000\|port.*8000\|PORT.*8000" . \
    --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include=".env*" \
    --exclude-dir={.git,node_modules,.next,venv,__pycache__} \
    --exclude="PORT_STANDARDS.md" --exclude="verify_ports.sh" 2>/dev/null | head -10
  ((errors++))
else
  echo -e "${GREEN}✅ No deprecated port 8000 references found${NC}"
fi
echo ""

# Check for deprecated port 3001
echo "🚫 Checking for deprecated port 3001..."
deprecated_3001=$(grep -r ":3001\|port.*3001\|PORT.*3001" . \
  --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include=".env*" \
  --exclude-dir={.git,node_modules,.next,venv,__pycache__} \
  --exclude="PORT_STANDARDS.md" --exclude="verify_ports.sh" 2>/dev/null | wc -l)

if [ "$deprecated_3001" -gt 0 ]; then
  echo -e "${RED}❌ Found $deprecated_3001 references to deprecated port 3001${NC}"
  grep -rn ":3001\|port.*3001\|PORT.*3001" . \
    --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include=".env*" \
    --exclude-dir={.git,node_modules,.next,venv,__pycache__} \
    --exclude="PORT_STANDARDS.md" --exclude="verify_ports.sh" 2>/dev/null | head -10
  ((errors++))
else
  echo -e "${GREEN}✅ No deprecated port 3001 references found${NC}"
fi
echo ""

# Verify standard ports are used
echo "✅ Verifying standard ports are used..."

# Check API port (8001)
api_port_refs=$(grep -r "8001" . \
  --include="*.py" --include=".env.example" --include="docker-compose.yml" \
  --exclude-dir={.git,node_modules,.next,venv,__pycache__} 2>/dev/null | wc -l)

if [ "$api_port_refs" -gt 0 ]; then
  echo -e "${GREEN}✅ API port 8001 found in configuration files${NC}"
else
  echo -e "${YELLOW}⚠️  Warning: API port 8001 not found in expected files${NC}"
  ((warnings++))
fi

# Check UI port (3000)
ui_port_refs=$(grep -r "3000" . \
  --include="*.env*" --include="docker-compose.yml" \
  --exclude-dir={.git,node_modules,.next,venv,__pycache__} 2>/dev/null | wc -l)

if [ "$ui_port_refs" -gt 0 ]; then
  echo -e "${GREEN}✅ UI port 3000 found in configuration files${NC}"
else
  echo -e "${YELLOW}⚠️  Warning: UI port 3000 not found in expected files${NC}"
  ((warnings++))
fi

echo ""
echo "======================================"
echo "📊 Verification Summary"
echo "======================================"
echo -e "Errors: ${RED}${errors}${NC}"
echo -e "Warnings: ${YELLOW}${warnings}${NC}"
echo ""

if [ "$errors" -eq 0 ] && [ "$warnings" -eq 0 ]; then
  echo -e "${GREEN}🎉 All port references are standardized!${NC}"
  exit 0
elif [ "$errors" -eq 0 ]; then
  echo -e "${YELLOW}⚠️  Port standardization complete with warnings${NC}"
  exit 0
else
  echo -e "${RED}❌ Port standardization has errors - please fix${NC}"
  exit 1
fi
