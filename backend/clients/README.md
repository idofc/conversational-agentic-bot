# Backend Clients Directory Structure

## Overview

The backend has been reorganized with all database and infrastructure clients moved to a dedicated `clients/` directory for better code organization.

## Directory Structure

```
backend/
├── clients/
│   ├── __init__.py              # Package initialization with exports
│   ├── database.py              # PostgreSQL database client (SQLAlchemy)
│   ├── redis_client.py          # Redis client for caching & rate limiting
│   └── elasticsearch_client.py  # Elasticsearch client for search
├── main.py                      # FastAPI application
├── seed_db.py                   # Database seeding script
└── ...
```

## Client Modules

### 1. Database Client (`database.py`)
- **Purpose:** PostgreSQL database operations with SQLAlchemy
- **Features:**
  - Async database sessions
  - ORM models (UseCaseDB, DocumentDB, ConversationDB, MessageDB, etc.)
  - pgvector support for embeddings
  - Database initialization

### 2. Redis Client (`redis_client.py`)
- **Purpose:** High-performance caching and rate limiting
- **Features:**
  - Conversation context caching (TTL: 10 minutes)
  - LLM response caching (TTL: 1 hour)
  - Session management (TTL: 30 minutes)
  - Rate limiting (60 requests/minute + burst)
  - Connection pooling (50 max connections)
  - Cache hit rate monitoring

### 3. Elasticsearch Client (`elasticsearch_client.py`)
- **Purpose:** Full-text search and analytics
- **Features:**
  - Message indexing with full-text search
  - Conversation title indexing
  - Advanced search with filters
  - Autocomplete suggestions
  - Analytics and aggregations
  - Highlight support

## Import Usage

### In Your Code

```python
# Import specific items
from clients.database import get_db, UseCaseDB, ConversationDB
from clients.redis_client import redis_client
from clients.elasticsearch_client import es_client

# Or use the package imports
from clients import redis_client, es_client, get_db
```

### Available Exports

From `clients/__init__.py`:
- `get_db` - Database session dependency
- `init_db` - Database initialization
- `UseCaseDB`, `DocumentDB`, `DocumentChunkDB`, `ConversationDB`, `MessageDB` - ORM models
- `AsyncSessionLocal` - Async session factory
- `redis_client` - Global Redis client instance
- `es_client` - Global Elasticsearch client instance

## Integration Flow

### Request Lifecycle with Clients

1. **Rate Limiting** (Redis)
   - Check request count per minute
   - Block if limit exceeded
   - Update counters

2. **Caching** (Redis)
   - Check for cached conversation context
   - Return cached data if available
   - Fall through to database on cache miss

3. **Database Operations** (PostgreSQL)
   - Query/update conversations and messages
   - Store persistent data
   - Vector search on document chunks

4. **Search & Analytics** (Elasticsearch)
   - Index new messages asynchronously
   - Provide full-text search capabilities
   - Generate analytics insights

5. **Cache Updates** (Redis)
   - Invalidate stale cache entries
   - Cache fresh data for subsequent requests

## Configuration

All clients are configured via environment variables in `.env`:

```bash
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/conversational_bot

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50

# Elasticsearch
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_INDEX_PREFIX=conversational_bot

# Cache TTL Settings
CACHE_TTL_SESSIONS=1800
CACHE_TTL_CONVERSATIONS=600
CACHE_TTL_LLM_RESPONSES=3600

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

## Health Monitoring

Check infrastructure health:

```bash
# Health check endpoint
curl http://localhost:8000/api/health

# Infrastructure stats
curl http://localhost:8000/api/stats
```

Response includes connection status for all three clients:
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected",
    "elasticsearch": "connected"
  }
}
```

## Migration Notes

### Files Updated
- ✅ `main.py` - Updated imports from `clients.database`, `clients.redis_client`, `clients.elasticsearch_client`
- ✅ `seed_db.py` - Updated import from `clients.database`
- ✅ Created `clients/__init__.py` - Package initialization

### No Changes Required
- Agent files continue to work as-is
- Document processor and embeddings modules unchanged
- Frontend remains unaffected

## Benefits of This Structure

1. **Better Organization:** Clear separation of infrastructure clients
2. **Easier Testing:** Mock entire client modules easily
3. **Scalability:** Easy to add new clients (MongoDB, RabbitMQ, etc.)
4. **Maintainability:** Related code grouped together
5. **Clear Boundaries:** Infrastructure vs business logic separation

## Next Steps

When adding new infrastructure clients:

1. Create new client module in `clients/` directory
2. Export from `clients/__init__.py`
3. Update imports in consuming modules
4. Add configuration to `.env`
5. Include health check in `/api/health` endpoint
