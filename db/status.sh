#!/bin/bash

echo "=========================================="
echo "Service Status"
echo "=========================================="
echo ""

# Check PostgreSQL
if docker ps --format '{{.Names}}' | grep -q 'conversational-bot-db'; then
    echo "✓ PostgreSQL: Running"
    DB_SIZE=$(docker exec conversational-bot-db psql -U postgres -d conversational_bot -t -c "SELECT pg_size_pretty(pg_database_size('conversational_bot'));" 2>/dev/null | xargs)
    CONNECTIONS=$(docker exec conversational-bot-db psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname='conversational_bot';" 2>/dev/null | xargs)
    echo "  Database Size: $DB_SIZE"
    echo "  Active Connections: $CONNECTIONS"
else
    echo "✗ PostgreSQL: Stopped"
fi

echo ""

# Check Redis
if docker ps --format '{{.Names}}' | grep -q 'conversational-bot-redis'; then
    echo "✓ Redis: Running"
    REDIS_MEMORY=$(docker exec conversational-bot-redis redis-cli info memory 2>/dev/null | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r' | xargs)
    REDIS_KEYS=$(docker exec conversational-bot-redis redis-cli dbsize 2>/dev/null | tr -d '\r')
    echo "  Memory Used: $REDIS_MEMORY"
    echo "  Keys Stored: $REDIS_KEYS"
else
    echo "✗ Redis: Stopped"
fi

echo ""

# Check Elasticsearch
if docker ps --format '{{.Names}}' | grep -q 'conversational-bot-elasticsearch'; then
    echo "✓ Elasticsearch: Running"
    ES_HEALTH=$(curl -s http://localhost:9200/_cluster/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    ES_DOCS=$(curl -s http://localhost:9200/_cat/count?format=json 2>/dev/null | grep -o '"count":"[^"]*"' | cut -d'"' -f4)
    echo "  Cluster Health: ${ES_HEALTH:-unknown}"
    echo "  Documents Indexed: ${ES_DOCS:-0}"
else
    echo "✗ Elasticsearch: Stopped"
fi

echo ""
echo "=========================================="
echo ""
echo "Container Resources:"
RUNNING_CONTAINERS=$(docker ps --format '{{.Names}}' | grep 'conversational-bot-')
if [ -n "$RUNNING_CONTAINERS" ]; then
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $RUNNING_CONTAINERS
else
    echo "No containers running"
fi
echo ""
