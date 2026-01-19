# Docker Setup Guide

This guide explains how to run the Biometric Processor API using Docker and Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum (16GB recommended)
- 4 CPU cores minimum

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd biometric-processor

# Copy environment file
cp .env.docker .env

# Edit .env with your configuration
nano .env
```

### 2. Start Services

```bash
# Start core services (PostgreSQL, Redis, API)
docker-compose up -d

# View logs
docker-compose logs -f api

# Check service health
docker-compose ps
```

### 3. Verify Installation

```bash
# Check API health
curl http://localhost:8080/api/v1/health

# View API documentation
open http://localhost:8080/docs
```

## Service Profiles

Docker Compose supports different profiles for different use cases:

### Core Services (Default)

```bash
docker-compose up -d
```

Includes:
- PostgreSQL with pgvector
- Redis
- Biometric API

### Development Mode

```bash
docker-compose --profile development up -d
```

Includes core services plus:
- API with hot reload (port 8081)

### With Management Tools

```bash
docker-compose --profile tools up -d
```

Includes core services plus:
- pgAdmin (PostgreSQL admin) - http://localhost:5050
- Redis Commander - http://localhost:8082

### With Monitoring

```bash
docker-compose --profile monitoring up -d
```

Includes core services plus:
- Prometheus (metrics) - http://localhost:9090
- Grafana (dashboards) - http://localhost:3000

### All Services

```bash
docker-compose --profile development --profile tools --profile monitoring up -d
```

## Service Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8080 | Main API endpoint |
| API Docs | http://localhost:8080/docs | Swagger UI |
| API Dev | http://localhost:8081 | Development API (hot reload) |
| pgAdmin | http://localhost:5050 | PostgreSQL admin panel |
| Redis Commander | http://localhost:8082 | Redis admin panel |
| Prometheus | http://localhost:9090 | Metrics collection |
| Grafana | http://localhost:3000 | Metrics visualization |

## Database Setup

### Automatic Initialization

The database is automatically initialized with:
- pgvector extension
- All required tables
- Indexes for performance
- Views for analytics

To reinitialize:

```bash
# Stop and remove volumes
docker-compose down -v

# Start fresh
docker-compose up -d
```

### Manual Database Access

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U biometric_user -d biometric_db

# View tables
\dt

# View indexes
\di

# Run query
SELECT COUNT(*) FROM face_embeddings;
```

### Using pgAdmin

1. Open http://localhost:5050
2. Login with credentials from `.env`:
   - Email: admin@biometric.local
   - Password: admin
3. Add server:
   - Host: postgres
   - Port: 5432
   - Database: biometric_db
   - Username: biometric_user
   - Password: (from .env)

## Redis Management

### CLI Access

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# View keys
KEYS *

# Get value
GET key_name

# Monitor commands
MONITOR
```

### Using Redis Commander

1. Open http://localhost:8082
2. Browse keys and values
3. Execute Redis commands

## Configuration

### Environment Variables

Edit `.env` to customize:

```bash
# Database
POSTGRES_DB=biometric_db
POSTGRES_USER=biometric_user
POSTGRES_PASSWORD=secure_password_here

# ML Models
FACE_DETECTION_BACKEND=retinaface
FACE_RECOGNITION_MODEL=Facenet512

# Performance
ASYNC_ML_ENABLED=true
ML_THREAD_POOL_SIZE=0  # 0 = auto-detect

# Security
API_KEY_ENABLED=false
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
```

### Scaling

Scale API instances:

```bash
# Scale to 3 instances
docker-compose up -d --scale api=3

# Check running instances
docker-compose ps api
```

## Development Workflow

### Hot Reload Development

```bash
# Start development environment
docker-compose --profile development up -d

# Make code changes - API will auto-reload
# View logs
docker-compose logs -f api-dev
```

### Running Tests

```bash
# Run tests inside container
docker-compose exec api pytest

# With coverage
docker-compose exec api pytest --cov=app --cov-report=html

# Run specific test
docker-compose exec api pytest tests/unit/test_enrollment.py
```

### Debugging

```bash
# View API logs
docker-compose logs -f api

# View all logs
docker-compose logs -f

# Exec into container
docker-compose exec api bash

# Check Python environment
docker-compose exec api python -c "import cv2; print(cv2.__version__)"
```

## Production Deployment

### Using Optimized Dockerfile

```bash
# Build production image
docker build -f Dockerfile.optimized --target runtime -t biometric-api:prod .

# Run production container
docker run -d \
  --name biometric-api \
  -p 8080:8080 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_HOST=redis \
  biometric-api:prod
```

### Multi-Stage Build

The optimized Dockerfile uses multi-stage builds:

1. **Builder stage**: Installs dependencies, compiles extensions
2. **Runtime stage**: Minimal production image
3. **Development stage**: Includes dev tools

```bash
# Build runtime image (smallest)
docker build -f Dockerfile.optimized --target runtime -t biometric-api:runtime .

# Build development image (with tools)
docker build -f Dockerfile.optimized --target development -t biometric-api:dev .
```

## Monitoring

### Prometheus Metrics

API exposes Prometheus metrics at `/metrics`:

```bash
# View metrics
curl http://localhost:8080/metrics

# In Prometheus UI
open http://localhost:9090
```

Available metrics:
- HTTP request duration
- Request count by endpoint
- Error rates
- ML inference time
- Database connection pool stats

### Grafana Dashboards

1. Open http://localhost:3000
2. Login (admin/admin)
3. Add Prometheus datasource:
   - URL: http://prometheus:9090
4. Import dashboards from `config/grafana/dashboards/`

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Check resource usage
docker stats

# Restart services
docker-compose restart

# Rebuild if needed
docker-compose up -d --build
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection
docker-compose exec api python -c "
from app.core.config import settings
print(settings.DATABASE_URL)
"
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Increase Docker memory limit in Docker Desktop settings
# Or reduce ML_THREAD_POOL_SIZE in .env
```

### Permission Issues

```bash
# Fix file permissions
sudo chown -R $USER:$USER uploads/

# Or run with sudo
sudo docker-compose up -d
```

### Network Issues

```bash
# Recreate network
docker-compose down
docker network prune
docker-compose up -d
```

## Maintenance

### Backup Database

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U biometric_user biometric_db > backup.sql

# Restore
docker-compose exec -T postgres psql -U biometric_user biometric_db < backup.sql
```

### Clear Redis Cache

```bash
# Flush all Redis data
docker-compose exec redis redis-cli FLUSHALL

# Flush specific database
docker-compose exec redis redis-cli -n 0 FLUSHDB
```

### Update Dependencies

```bash
# Rebuild images with latest dependencies
docker-compose build --no-cache

# Pull latest base images
docker-compose pull

# Restart with new images
docker-compose up -d
```

### Clean Up

```bash
# Stop and remove containers
docker-compose down

# Remove volumes (data will be lost!)
docker-compose down -v

# Remove images
docker rmi $(docker images -q biometric-processor*)

# Clean up Docker system
docker system prune -a
```

## Performance Tuning

### PostgreSQL

Edit `docker-compose.yml` to adjust PostgreSQL settings:

```yaml
services:
  postgres:
    environment:
      POSTGRES_SHARED_BUFFERS: 512MB
      POSTGRES_WORK_MEM: 8MB
      POSTGRES_MAX_CONNECTIONS: 200
```

### Redis

Adjust Redis configuration in `docker-compose.yml`:

```yaml
services:
  redis:
    command: >
      redis-server
      --maxmemory 1gb
      --maxmemory-policy allkeys-lru
```

### API

Configure resource limits:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
```

## Security Best Practices

### Production Checklist

- [ ] Change default passwords in `.env`
- [ ] Enable API key authentication (`API_KEY_ENABLED=true`)
- [ ] Use HTTPS (`REQUIRE_HTTPS=true`)
- [ ] Restrict CORS origins
- [ ] Enable rate limiting
- [ ] Use non-root user (already configured)
- [ ] Keep base images updated
- [ ] Use secrets management (Docker secrets, Vault)
- [ ] Enable audit logging
- [ ] Regular security scans

### Docker Secrets (Recommended for Production)

```yaml
services:
  api:
    secrets:
      - db_password
      - api_key
    environment:
      DATABASE_PASSWORD_FILE: /run/secrets/db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
  api_key:
    file: ./secrets/api_key.txt
```

## Additional Resources

- [Architecture Documentation](./ARCHITECTURE.md)
- [API Documentation](http://localhost:8080/docs)
- [Kubernetes Deployment](./k8s/)
- [Contributing Guidelines](./CONTRIBUTING.md)

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/biometric-processor/issues
- Documentation: https://docs.biometric-processor.io
- Email: support@biometric-processor.io
