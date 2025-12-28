# Database Setup Instructions

## Enable pgvector Extension

The biometric API requires the pgvector extension for vector similarity search. Follow these steps to enable it:

### Option 1: Google Cloud Console (Recommended)

1. Go to [Cloud SQL Instances](https://console.cloud.google.com/sql/instances?project=fivucsas)
2. Click on `biometric-db`
3. Click "Cloud SQL Studio" in the left sidebar
4. Select database: `biometric`
5. Run the following SQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector CASCADE;
```

6. Verify with:
```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

### Option 2: Using Cloud SQL Proxy (Local)

1. Download Cloud SQL Proxy from [GitHub](https://github.com/GoogleCloudPlatform/cloud-sql-proxy/releases)

2. Start the proxy:
```bash
cloud-sql-proxy fivucsas:europe-west1:biometric-db --port=5432
```

3. Connect with psql:
```bash
psql "host=127.0.0.1 port=5432 user=postgres dbname=biometric password=BiometricSecure2024!"
```

4. Run the init script:
```bash
psql "host=127.0.0.1 port=5432 user=postgres dbname=biometric" -f scripts/init-database.sql
```

### Option 3: Using gcloud (with authorized network)

1. Add your IP to authorized networks:
```bash
gcloud sql instances patch biometric-db \
    --authorized-networks=$(curl -s ifconfig.me)/32 \
    --project=fivucsas
```

2. Connect:
```bash
gcloud sql connect biometric-db --database=biometric --user=postgres --project=fivucsas
```

3. Run the SQL commands from `scripts/init-database.sql`

## Verify Setup

After enabling the extension, test the API:

```bash
curl https://biometric-api-902542798396.europe-west1.run.app/api/v1/health
```

The health check should return:
```json
{"status":"healthy","version":"1.0.0","model":"Facenet","detector":"opencv"}
```

## Troubleshooting

### Error: "unknown type: public.vector"

This means the pgvector extension is not installed. Run:
```sql
CREATE EXTENSION IF NOT EXISTS vector CASCADE;
```

### Error: "permission denied to create extension"

Your database user needs superuser privileges. In Cloud SQL, the `postgres` user has these privileges by default.

### Connection Issues

1. Check that Cloud SQL instance is running
2. Verify VPC connector is configured
3. Check authorized networks include Cloud Run's egress IPs
