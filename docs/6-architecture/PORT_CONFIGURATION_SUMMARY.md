# 🎯 PORT CONFIGURATION - CRITICAL REFERENCE

**Last Updated:** 2025-12-24
**Status:** ✅ ALL PORTS STANDARDIZED
**Action Required:** Read this FIRST before starting any service

---

## ⚠️ CRITICAL - READ THIS FIRST

**THE ONLY OFFICIAL PORTS TO USE:**

```
┌─────────────────────────────────────────────────────────┐
│  SERVICE             │  PORT  │  URL                    │
├─────────────────────────────────────────────────────────┤
│  Biometric API       │  8001  │  http://localhost:8001  │
│  Demo UI             │  3000  │  http://localhost:3000  │
│  PostgreSQL          │  5432  │  localhost:5432         │
│  Redis               │  6379  │  localhost:6379         │
│  Prometheus          │  9090  │  http://localhost:9090  │
└─────────────────────────────────────────────────────────┘
```

**🚫 NEVER USE PORT 8000 - IT IS DEPRECATED!**

---

## 📋 QUICK START CHECKLIST

Before starting development:

- [ ] 1. Verify `.env` has `API_PORT=8001`
- [ ] 2. Verify `demo-ui/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8001`
- [ ] 3. Check no other service is using port 8001
- [ ] 4. Start services in this order:
  ```bash
  # 1. Database & Cache
  docker-compose up -d postgres redis

  # 2. API (choose ONE method):
  # Method A: Using venv
  .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

  # Method B: Using Docker
  docker-compose up -d biometric-api

  # 3. Demo UI
  cd demo-ui && npm run dev
  ```
- [ ] 5. Verify API is accessible: http://localhost:8001/api/v1/health
- [ ] 6. Verify UI is accessible: http://localhost:3000

---

## 🔍 FILES UPDATED (2025-12-24)

### ✅ Configuration Files Fixed

| File | Change Made | Status |
|------|------------|--------|
| `.env` | `API_PORT=8000` → `API_PORT=8001` | ✅ FIXED |
| `demo-ui/.env.local` | `localhost:8000` → `localhost:8001` | ✅ FIXED |
| `demo-ui/.env.example` | `localhost:8000` → `localhost:8001` | ✅ FIXED |
| `.env.example` | Already correct (8001) | ✅ OK |
| `docker-compose.yml` | Already correct (8001) | ✅ OK |
| `app/core/config.py` | Already correct (default=8001) | ✅ OK |

### ✅ Documentation Files Verified

| File | Port Referenced | Status |
|------|----------------|--------|
| `PORT_STANDARDS.md` | 8001 (Official Standard) | ✅ OK |
| `README.md` | 8001 | ✅ OK |
| `QUICK_START.md` | 8001 | ✅ OK |
| `docs/api/API_DOCUMENTATION.md` | 8001 | ✅ OK |

### ✅ Test/Demo Files Verified

| File | Port Referenced | Status |
|------|----------------|--------|
| `demo/utils/config.py` | 8001 | ✅ OK |
| `demo/utils/api_client.py` | 8001 | ✅ OK |
| `tests/load/locustfile.py` | 8001 | ✅ OK |

---

## 🚨 COMMON MISTAKES TO AVOID

### ❌ WRONG - Using Port 8000

```bash
# DON'T DO THIS:
uvicorn app.main:app --port 8000  # ❌ WRONG PORT!
NEXT_PUBLIC_API_URL=http://localhost:8000  # ❌ WRONG!
```

### ✅ CORRECT - Using Port 8001

```bash
# DO THIS INSTEAD:
uvicorn app.main:app --port 8001  # ✅ CORRECT
NEXT_PUBLIC_API_URL=http://localhost:8001  # ✅ CORRECT
```

---

## 🔧 ENVIRONMENT VARIABLES - COMPLETE REFERENCE

### API Server Configuration

```bash
# .env file (ROOT directory)
API_PORT=8001                                    # ✅ MUST be 8001
HOST=0.0.0.0                                     # Listen on all interfaces
DATABASE_URL=postgresql+asyncpg://biometric:biometric@localhost:5432/biometric
REDIS_HOST=localhost
REDIS_PORT=6379                                  # Standard Redis port
```

### Demo UI Configuration

```bash
# demo-ui/.env.local file
NEXT_PUBLIC_API_URL=http://localhost:8001       # ✅ MUST be 8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001           # ✅ MUST be 8001
```

---

## 🐳 DOCKER COMPOSE - PORT MAPPING

```yaml
# docker-compose.yml (already correct)
services:
  biometric-api:
    ports:
      - "8001:8001"  # ✅ External:Internal both 8001
    environment:
      - API_PORT=8001  # ✅ Internal port

  demo-ui:
    ports:
      - "3000:3000"  # ✅ Standard Next.js port

  postgres:
    ports:
      - "5432:5432"  # ✅ Standard PostgreSQL port

  redis:
    ports:
      - "6379:6379"  # ✅ Standard Redis port
```

---

## 🧪 TESTING PORT CONFIGURATION

### 1. Test API Port

```bash
# Should show "healthy" on port 8001
curl http://localhost:8001/api/v1/health

# Expected response:
{
  "status": "healthy",
  "version": "1.0.0",
  "model": "Facenet",
  "detector": "opencv"
}
```

### 2. Test UI Port

```bash
# Should return HTML (Next.js app)
curl http://localhost:3000
```

### 3. Test Database Port

```bash
# Should connect successfully
docker exec biometric-postgres psql -U biometric -d biometric -c "SELECT 1;"
```

### 4. Test Redis Port

```bash
# Should return "PONG"
docker exec biometric-redis redis-cli ping
```

---

## 🔍 FINDING PORT CONFLICTS

### Check if Port 8001 is Already in Use

```bash
# Windows:
netstat -ano | findstr ":8001"

# Linux/Mac:
lsof -i :8001
# Or: netstat -tulpn | grep 8001
```

### If Port 8001 is Busy

```bash
# Option 1: Kill the process using the port
# Windows: taskkill /PID <PID> /F
# Linux/Mac: kill -9 <PID>

# Option 2: Find what's using it and stop it properly
# Example: Stop another development server
```

**⚠️ DO NOT change the standard port. Fix the conflict instead.**

---

## 📚 WHY THESE SPECIFIC PORTS?

### Port 8001 (API)
- ✅ Avoids conflicts with common dev servers (8000, 8080)
- ✅ Clear separation from Identity Core API (8080)
- ✅ Standard microservice port range (8000-8999)
- ✅ Less common than 8000, fewer conflicts

### Port 3000 (UI)
- ✅ Next.js default port
- ✅ Industry standard for React/Next.js apps
- ✅ Widely recognized by developers

### Port 5432 (PostgreSQL)
- ✅ Official PostgreSQL default port
- ✅ Standard across all PostgreSQL installations

### Port 6379 (Redis)
- ✅ Official Redis default port
- ✅ Universal Redis standard

---

## 🎓 DEVELOPER GUIDELINES

### When Starting New Development

1. **ALWAYS** check `PORT_STANDARDS.md` first
2. **NEVER** hardcode port 8000 anywhere
3. **ALWAYS** use environment variables for ports
4. **VERIFY** configuration before starting services

### When Adding New Services

1. Add the port to `PORT_STANDARDS.md`
2. Update this summary document
3. Document in `README.md`
4. Update `docker-compose.yml`
5. Add to environment variable examples

### When Updating Documentation

1. Search for `8000` - should only appear in:
   - `PORT_STANDARDS.md` (in "deprecated" section)
   - `RELEASE_NOTES.md` (in changelog)
   - This file (in "wrong" examples)
2. Replace any other occurrences with `8001`

---

## 🔐 PRODUCTION CONSIDERATIONS

### Port Mapping (Production)

```bash
# Production typically uses reverse proxy
# External (Internet) → Internal (Container)

HTTPS/443 → 8001 (API)
HTTPS/443 → 3000 (UI)

# Database & Redis should NOT be exposed externally
# They only communicate internally within Docker network
```

### Environment-Specific Ports

```bash
# Development
API: http://localhost:8001
UI:  http://localhost:3000

# Staging
API: https://api-staging.example.com  (→ 8001)
UI:  https://app-staging.example.com  (→ 3000)

# Production
API: https://api.example.com  (→ 8001)
UI:  https://app.example.com  (→ 3000)
```

---

## ✅ VERIFICATION COMMANDS

Run these commands to verify all ports are correct:

```bash
# 1. Check for deprecated port 8000 references
# (Should return empty or only in PORT_STANDARDS.md/RELEASE_NOTES)
grep -r "8000" . --exclude-dir={.git,node_modules,.venv,__pycache__} \
  --exclude="*.{log,pyc}" | grep -v "PORT_STANDARDS.md" | grep -v "RELEASE_NOTES"

# 2. Verify .env file
grep "API_PORT" .env
# Should show: API_PORT=8001

# 3. Verify demo-ui config
grep "NEXT_PUBLIC_API_URL" demo-ui/.env.local
# Should show: NEXT_PUBLIC_API_URL=http://localhost:8001

# 4. Verify docker-compose
grep -A 1 "biometric-api:" docker-compose.yml | grep ports
# Should show: - "8001:8001"

# 5. Verify Python config
grep "API_PORT.*Field.*default" app/core/config.py
# Should show: API_PORT: int = Field(default=8001...)
```

---

## 📞 TROUBLESHOOTING

### "Connection Refused" Error

**Symptom:** UI shows "Failed to load resource: net::ERR_CONNECTION_REFUSED"

**Cause:** UI is trying to connect to wrong port

**Solution:**
1. Check `demo-ui/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8001`
2. Restart the UI: `cd demo-ui && npm run dev`
3. Hard refresh browser: Ctrl+Shift+R

### "Port Already in Use" Error

**Symptom:** `Error: listen EADDRINUSE: address already in use :::8001`

**Cause:** Another process is using port 8001

**Solution:**
```bash
# Find what's using the port
netstat -ano | findstr ":8001"

# Kill the process (replace PID with actual PID)
taskkill /PID <PID> /F
```

### API Works on 8000 but Not 8001

**Cause:** `.env` file has wrong port

**Solution:**
1. Open `.env` file
2. Change `API_PORT=8000` to `API_PORT=8001`
3. Restart the API server

---

## 📝 REFERENCES

- **Official Standard:** See `PORT_STANDARDS.md`
- **API Documentation:** See `docs/api/API_DOCUMENTATION.md`
- **Quick Start Guide:** See `QUICK_START.md`
- **Docker Setup:** See `docker-compose.yml`

---

## ⚡ SUMMARY

**REMEMBER THESE THREE NUMBERS:**

```
API:  8001  ← NOT 8000!
UI:   3000
DB:   5432
```

**IF IN DOUBT:** Check `PORT_STANDARDS.md` or this file.

**NEVER COMMIT:** Configuration with port 8000 for the API.

---

**Last Verified:** 2025-12-24
**Next Review:** When adding new services
**Maintained By:** Development Team
**Status:** ✅ ENFORCED - ALL CONFIGURATIONS STANDARDIZED
