# Port Standardization - Biometric Processor

**Date:** 2025-12-24
**Status:** Official Port Standard

---

## 🎯 **Official Port Allocation**

This document defines the **official port standards** for all services in the biometric processor ecosystem. All documentation, configuration, and deployment files MUST use these ports.

### **Production Port Standards**

| Service | Port | Protocol | Purpose | Status |
|---------|------|----------|---------|--------|
| **Biometric API** | **8001** | HTTP/HTTPS | Main API service | ✅ STANDARD |
| **Demo UI (Next.js)** | **3000** | HTTP/HTTPS | Web interface | ✅ STANDARD |
| **PostgreSQL** | **5432** | TCP | Database (pgvector) | ✅ STANDARD |
| **Redis** | **6379** | TCP | Cache & rate limiting | ✅ STANDARD |
| **Prometheus** | **9090** | HTTP | Metrics collection | ✅ STANDARD |
| **Admin Panel** | **8080** | HTTP | Identity Core API | 📝 FUTURE |

---

## 🚫 **DEPRECATED Ports**

**DO NOT USE:**
- ❌ **8000** - Old API port (replaced by 8001)
- ❌ **3001** - Alternative UI port (use 3000 only)
- ❌ **8080** - Conflicted with admin (reserved for Identity Core)

**Why 8001 instead of 8000?**
- Avoids common conflicts with development servers
- Clear separation from Identity Core API (8080)
- Consistent with microservice port allocation

---

## 📋 **Port Allocation Rules**

### **Development Environment**

```bash
# Biometric Processor API
http://localhost:8001

# Demo UI (Next.js)
http://localhost:3000

# PostgreSQL
postgresql://localhost:5432/biometric

# Redis
redis://localhost:6379

# Prometheus
http://localhost:9090
```

### **Docker/Container Environment**

```yaml
services:
  biometric-api:
    ports:
      - "8001:8001"  # External:Internal

  demo-ui:
    ports:
      - "3000:3000"

  postgres:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"

  prometheus:
    ports:
      - "9090:9090"
```

### **Kubernetes Environment**

```yaml
# Service ports (ClusterIP)
- biometric-api: 8001
- demo-ui: 3000
- postgres: 5432 (internal only)
- redis: 6379 (internal only)
- prometheus: 9090 (internal only)

# Ingress (external access)
- https://api.example.com -> biometric-api:8001
- https://app.example.com -> demo-ui:3000
```

---

## 🔧 **Configuration Updates Required**

### **1. Environment Variables**

```bash
# .env
API_PORT=8001                    # ✅ CORRECT
# API_PORT=8000                  # ❌ WRONG

# demo-ui/.env
NEXT_PUBLIC_API_URL=http://localhost:8001    # ✅ CORRECT
# NEXT_PUBLIC_API_URL=http://localhost:8000  # ❌ WRONG
```

### **2. Docker Compose**

```yaml
# docker-compose.yml
biometric-api:
  ports:
    - "8001:8001"     # ✅ CORRECT
    # - "8000:8000"   # ❌ WRONG
  environment:
    - API_PORT=8001   # ✅ CORRECT
```

### **3. Application Code**

```python
# app/core/config.py
API_PORT: int = Field(default=8001)  # ✅ CORRECT
# API_PORT: int = Field(default=8000)  # ❌ WRONG
```

### **4. Documentation**

All documentation MUST use:
- API examples: `http://localhost:8001`
- UI examples: `http://localhost:3000`
- Never reference port 8000 or 3001

---

## 📝 **Files to Update**

### **Critical Files (MUST Update)**

1. **Configuration:**
   - ✅ `.env.example`
   - ✅ `app/core/config.py`
   - ✅ `demo-ui/.env.example`

2. **Deployment:**
   - ✅ `docker-compose.yml`
   - ✅ `k8s/base/deployment.yaml`
   - ✅ `k8s/base/service.yaml`

3. **Documentation:**
   - ✅ `README.md`
   - ✅ `QUICK_START.md`
   - ✅ `docs/api/API_DOCUMENTATION.md`
   - All `*.md` files with port references

4. **Test Files:**
   - ✅ `tests/load/locustfile.py`
   - ✅ `demo/utils/config.py`
   - ✅ Test scripts (`test_*.py`)

---

## ✅ **Verification Checklist**

After updating ports, verify:

```bash
# 1. Search for deprecated ports
grep -r "8000\|3001" . --exclude-dir={.git,node_modules} | grep -v "PORT_STANDARDS.md"
# Should return: No results (except in history/changelog)

# 2. Verify API starts on correct port
uvicorn app.main:app --reload
# Should show: Uvicorn running on http://0.0.0.0:8001

# 3. Verify Docker Compose
docker-compose up
# biometric-api should expose 8001
# demo-ui should expose 3000

# 4. Test API access
curl http://localhost:8001/api/v1/health
# Should return: 200 OK

# 5. Test UI access
curl http://localhost:3000
# Should return: HTML (Next.js app)
```

---

## 🔄 **Migration Guide**

### **If Currently Using Port 8000:**

1. **Stop all services:**
   ```bash
   docker-compose down
   # Or: Ctrl+C if running locally
   ```

2. **Update configuration:**
   ```bash
   # Update .env
   sed -i 's/8000/8001/g' .env

   # Update demo-ui/.env
   sed -i 's/8000/8001/g' demo-ui/.env
   ```

3. **Restart services:**
   ```bash
   docker-compose up -d
   # Or: uvicorn app.main:app --reload
   ```

4. **Update bookmarks/scripts:**
   - Change browser bookmarks from :8000 to :8001
   - Update any custom scripts or automation

---

## 🌐 **URL Standards**

### **Development URLs**

```
API Base URL:    http://localhost:8001
API Docs:        http://localhost:8001/docs
API Health:      http://localhost:8001/api/v1/health

Demo UI:         http://localhost:3000
Metrics:         http://localhost:9090
```

### **Production URLs** (example)

```
API:             https://api.biometric.example.com
Demo UI:         https://app.biometric.example.com
Admin:           https://admin.identity.example.com
```

---

## 🔒 **Security Considerations**

### **Firewall Rules**

```bash
# Allow only necessary ports
ufw allow 8001/tcp  # API
ufw allow 3000/tcp  # UI (if public)
ufw deny 5432/tcp   # PostgreSQL (internal only)
ufw deny 6379/tcp   # Redis (internal only)
```

### **Docker Network Isolation**

```yaml
# docker-compose.yml
networks:
  backend:  # Internal only - Postgres, Redis
  frontend: # Public - API, UI
```

**Rules:**
- PostgreSQL & Redis: Backend network only (no external exposure)
- API: Both networks (frontend for clients, backend for DB/Redis)
- UI: Frontend network only

---

## 📊 **Port Conflict Resolution**

### **Common Conflicts**

| Port | Common Conflicts | Resolution |
|------|-----------------|------------|
| 8001 | Rarely conflicts | ✅ Safe choice |
| 3000 | React, Remix dev servers | Stop other dev servers first |
| 5432 | Other PostgreSQL | Use Docker or change to 5433 |
| 6379 | Other Redis | Use Docker or change to 6380 |

### **If Port 8001 is Already in Use**

```bash
# Find what's using the port
lsof -i :8001
# Or: netstat -tulpn | grep 8001

# Option 1: Kill the process
kill -9 <PID>

# Option 2: Use alternative port temporarily
API_PORT=8002 uvicorn app.main:app --reload
```

**Note:** Do NOT change the standard. Fix the conflict instead.

---

## 📚 **References**

- **Why these ports?**
  - 8001: Common microservice port, avoids conflicts
  - 3000: Next.js default, widely adopted
  - 5432: PostgreSQL standard
  - 6379: Redis standard
  - 9090: Prometheus standard

- **Industry Standards:**
  - 80/443: HTTP/HTTPS (production with reverse proxy)
  - 8000-8999: Application servers
  - 3000-3999: Frontend frameworks
  - 5000-5999: Databases
  - 6000-6999: Caches
  - 9000-9999: Monitoring/metrics

---

## ✨ **Summary**

**Official Ports:**
- 🔵 API: **8001**
- 🟢 UI: **3000**
- 🟣 PostgreSQL: **5432**
- 🔴 Redis: **6379**
- 🟠 Prometheus: **9090**

**Deprecated:**
- ❌ 8000 (old API)
- ❌ 3001 (alternative UI)

**All systems MUST use these standardized ports for consistency.**

---

**Last Updated:** 2025-12-24
**Approved By:** Development Team
**Status:** **MANDATORY - ENFORCE IN ALL ENVIRONMENTS**
