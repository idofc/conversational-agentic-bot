#!/bin/bash

echo "Starting all services (PostgreSQL, Redis, Elasticsearch)..."

# Function to wait for all services to be healthy
wait_for_services() {
    echo ""
    echo "Waiting for services to be ready..."
    
    # Wait for PostgreSQL
    echo -n "PostgreSQL: "
    for i in {1..30}; do
        if docker exec conversational-bot-db pg_isready -U postgres > /dev/null 2>&1; then
            echo "✓ Ready"
            break
        fi
        echo -n "."
        sleep 1
        if [ $i -eq 30 ]; then
            echo " ✗ Timeout"
            return 1
        fi
    done
    
    # Wait for Redis
    echo -n "Redis: "
    for i in {1..30}; do
        if docker exec conversational-bot-redis redis-cli ping > /dev/null 2>&1; then
            echo "✓ Ready"
            break
        fi
        echo -n "."
        sleep 1
        if [ $i -eq 30 ]; then
            echo " ✗ Timeout"
            return 1
        fi
    done
    
    # Wait for Elasticsearch (takes longer to be fully ready)
    echo -n "Elasticsearch: "
    for i in {1..60}; do
        HEALTH=$(curl -s http://localhost:9200/_cluster/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        if [ "$HEALTH" = "green" ] || [ "$HEALTH" = "yellow" ]; then
            echo "✓ Ready (status: $HEALTH)"
            break
        fi
        echo -n "."
        sleep 2
        if [ $i -eq 60 ]; then
            echo " ✗ Timeout"
            return 1
        fi
    done
    
    echo ""
    echo "✓ All services are healthy and ready"
}

# Check if containers exist and handle accordingly
start_or_create_services() {
    # Check if any container exists
    if docker ps -a --format '{{.Names}}' | grep -q 'conversational-bot-'; then
        # Check running containers
        RUNNING=$(docker ps --format '{{.Names}}' | grep 'conversational-bot-' | wc -l | tr -d ' ')
        TOTAL=$(docker ps -a --format '{{.Names}}' | grep 'conversational-bot-' | wc -l | tr -d ' ')
        
        if [ "$RUNNING" -eq "$TOTAL" ] && [ "$RUNNING" -eq 3 ]; then
            echo "✓ All services are already running"
            # Still wait for health checks to ensure they're ready
            wait_for_services
            return 0
        else
            echo "Starting existing containers..."
            cd "$(dirname "$0")/.."
            docker compose start
            echo "✓ Services started successfully"
            # Wait for all services to be healthy
            wait_for_services
        fi
    else
        # No containers exist, create them
        echo "Creating and starting service containers..."
        cd "$(dirname "$0")/.."
        docker compose up -d
        
        # Wait for services to be ready
        wait_for_services
        
        # Initialize database with schema
        echo ""
        echo "Initializing database schema..."
        docker exec conversational-bot-db psql -U postgres -c "CREATE DATABASE conversational_bot;" 2>/dev/null || echo "Database already exists"
        docker exec -i conversational-bot-db psql -U postgres -d conversational_bot < "$(dirname "$0")/init.sql"
        
        echo "✓ All services created and initialized successfully"
    fi
}

start_or_create_services

# Show connection info
echo ""
echo "=========================================="
echo "Service Connection Info:"
echo "=========================================="
echo ""
echo "PostgreSQL:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: conversational_bot"
echo "  User: postgres"
echo "  Password: postgres"
echo "  Connect: psql -h localhost -U postgres -d conversational_bot"
echo ""
echo "Redis:"
echo "  Host: localhost"
echo "  Port: 6379"
echo "  Connect: redis-cli"
echo "  Test: redis-cli ping"
echo ""
echo "Elasticsearch:"
echo "  Host: localhost"
echo "  Port: 9200 (HTTP), 9300 (Transport)"
echo "  Health: curl http://localhost:9200/_cluster/health"
echo "  Info: curl http://localhost:9200"
echo ""
echo "=========================================="
echo ""
echo "Resource Usage:"
echo "  PostgreSQL: ~2GB RAM, 2 CPUs"
echo "  Redis: ~512MB RAM, 1 CPU"
echo "  Elasticsearch: ~2GB RAM, 2 CPUs"
echo "  Total: ~4.5GB RAM, 5 CPUs"
echo ""
echo "View logs: docker compose logs -f [service-name]"
echo "Stop all: ./stop-db.sh"
echo "=========================================="
