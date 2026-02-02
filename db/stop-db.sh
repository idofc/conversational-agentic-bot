#!/bin/bash

echo "Stopping all services (PostgreSQL, Redis, Elasticsearch)..."

# Check if any containers are running
if docker ps --format '{{.Names}}' | grep -q 'conversational-bot-'; then
    cd "$(dirname "$0")/.."
    docker compose stop
    echo "✓ All services stopped successfully"
else
    echo "No services are currently running"
fi

echo ""
echo "To start services again, run: ./start-db.sh"
echo "To remove containers and data, run: cd .. && docker compose down -v"
