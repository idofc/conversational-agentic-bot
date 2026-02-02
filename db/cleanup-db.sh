#!/bin/bash

echo "WARNING: This will stop and remove all containers and volumes!"
echo "All data will be permanently deleted."
read -p "Are you sure? (yes/no): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo "Cleanup cancelled"
    exit 0
fi

echo ""
echo "Stopping and removing all services..."
cd "$(dirname "$0")/.."
docker compose down -v

echo "✓ All services and data removed successfully"
echo ""
echo "To start fresh, run: ./db/start-db.sh"
