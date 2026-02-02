# High-Volume Infrastructure Setup

This document describes the multi-tier database architecture for handling 10K-100K concurrent users.

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  Application                     │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────────┐
        ▼             ▼                 ▼
    [Redis]    [PostgreSQL]    [Elasticsearch]
     Cache       Primary DB       Search & Analytics
```

## Services

### PostgreSQL (Primary Database)
- **Port:** 5432
- **Purpose:** Source of truth, vector search with pgvector
- **Resources:** 2GB RAM, 2 CPUs
- **Optimizations:**
  - Max 200 connections
  - 256MB shared buffers
  - 1GB effective cache

### Redis (Caching & Sessions)
- **Port:** 6379
- **Purpose:** Session management, rate limiting, hot data caching
- **Resources:** 512MB RAM, 1 CPU
- **Features:**
  - LRU eviction policy
  - AOF persistence
  - Session TTL: 30 minutes
  - LLM response cache: 1 hour

### Elasticsearch (Search & Analytics)
- **Port:** 9200 (HTTP), 9300 (Transport)
- **Purpose:** Full-text search, conversation discovery, analytics
- **Resources:** 2GB RAM, 2 CPUs
- **Features:**
  - 30% index buffer
  - 15% query cache
  - Optimized for document indexing

## Quick Start

### Start All Services
```bash
cd db
./start-db.sh
```

### Check Status
```bash
cd db
./status.sh
```

### Stop Services
```bash
cd db
./stop-db.sh
```

### Clean Up Everything
```bash
cd db
./cleanup-db.sh  # WARNING: Deletes all data
```

## Service Health Checks

### PostgreSQL
```bash
docker exec conversational-bot-db pg_isready -U postgres
# or
psql -h localhost -U postgres -d conversational_bot -c "SELECT 1"
```

### Redis
```bash
docker exec conversational-bot-redis redis-cli ping
# Expected: PONG
```

### Elasticsearch
```bash
curl http://localhost:9200/_cluster/health
# Expected: {"status":"green",...}
```

## Environment Configuration

The following environment variables are configured in `backend/.env`:

### Redis Configuration
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50
```

### Elasticsearch Configuration
```bash
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_INDEX_PREFIX=conversational_bot
```

### Cache TTL Settings
```bash
CACHE_TTL_SESSIONS=1800          # 30 minutes
CACHE_TTL_CONVERSATIONS=600       # 10 minutes
CACHE_TTL_LLM_RESPONSES=3600      # 1 hour
```

### Rate Limiting
```bash
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

## Resource Requirements

**Total System Resources:**
- **RAM:** ~4.5GB
- **CPU:** 5 cores
- **Disk:** Variable (depends on data volume)

**Minimum Server Specs for 10K-100K users:**
- 8GB RAM
- 4-8 CPU cores
- 50GB SSD storage

## Data Flow Examples

### User Authentication & Session
```
1. User logs in → Validate in PostgreSQL
2. Create session → Store in Redis (30min TTL)
3. Every request → Check Redis for session
```

### Chat Message Flow
```
1. User sends message
2. Check rate limit in Redis
3. Load conversation context from Redis (or PostgreSQL if cache miss)
4. Generate LLM response (check Redis cache first)
5. Save message to PostgreSQL
6. Index message in Elasticsearch (async)
7. Update Redis cache
```

### Search Flow
```
Sidebar search (titles only) → PostgreSQL
Full conversation search → Elasticsearch
Advanced filters → Elasticsearch
```

## Monitoring

### Real-time Metrics
```bash
# View service status and resource usage
./db/status.sh

# Watch container logs
docker compose logs -f postgres
docker compose logs -f redis
docker compose logs -f elasticsearch
```

### Database Size
```bash
docker exec conversational-bot-db psql -U postgres -d conversational_bot -c \
  "SELECT pg_size_pretty(pg_database_size('conversational_bot'));"
```

### Redis Memory Usage
```bash
docker exec conversational-bot-redis redis-cli info memory | grep used_memory_human
```

### Elasticsearch Cluster Health
```bash
curl -s http://localhost:9200/_cluster/health | jq
```

## Scaling Beyond 100K Users

When you exceed 100K concurrent users:

### PostgreSQL
- Add read replicas
- Implement connection pooling (PgBouncer)
- Consider partitioning large tables

### Redis
- Migrate to Redis Cluster (sharding)
- Separate cache and session instances

### Elasticsearch
- Create multi-node cluster
- Add more data nodes
- Implement index lifecycle policies

## Troubleshooting

### Services Won't Start
```bash
# Check if ports are already in use
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :9200  # Elasticsearch

# Check Docker resources
docker system df
docker system prune  # Clean up if needed
```

### Elasticsearch Memory Issues
```bash
# Increase heap size in docker-compose.yml
ES_JAVA_OPTS=-Xms2g -Xmx2g  # Change to -Xms4g -Xmx4g
```

### PostgreSQL Connection Limit
```bash
# Check current connections
docker exec conversational-bot-db psql -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity;"

# View connection details
docker exec conversational-bot-db psql -U postgres -c \
  "SELECT * FROM pg_stat_activity WHERE datname='conversational_bot';"
```

## Backup & Recovery

### PostgreSQL Backup
```bash
docker exec conversational-bot-db pg_dump -U postgres conversational_bot > backup.sql
```

### PostgreSQL Restore
```bash
docker exec -i conversational-bot-db psql -U postgres conversational_bot < backup.sql
```

### Redis Backup
```bash
docker exec conversational-bot-redis redis-cli SAVE
docker cp conversational-bot-redis:/data/dump.rdb ./redis-backup.rdb
```

### Elasticsearch Snapshot
```bash
# Configure snapshot repository first, then:
curl -X PUT "localhost:9200/_snapshot/my_backup/snapshot_1?wait_for_completion=true"
```

## Next Steps

1. **Install Python dependencies:**
   ```bash
   cd backend
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Implement Redis caching** in your application
3. **Implement Elasticsearch indexing** for messages
4. **Add rate limiting** middleware
5. **Implement session management** with Redis

## Support

For issues or questions:
- Check logs: `docker compose logs -f [service-name]`
- Run status check: `./db/status.sh`
- Review this documentation
