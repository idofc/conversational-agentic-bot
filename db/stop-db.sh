#!/bin/bash

echo "Stopping PostgreSQL database..."

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q '^conversational-bot-db$'; then
    docker stop conversational-bot-db
    echo "✓ Database stopped successfully"
else
    echo "Database is not running"
fi
