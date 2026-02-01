#!/bin/bash

echo "Starting PostgreSQL database..."

# Check if container exists
if docker ps -a --format '{{.Names}}' | grep -q '^conversational-bot-db$'; then
    # Container exists, check if it's running
    if docker ps --format '{{.Names}}' | grep -q '^conversational-bot-db$'; then
        echo "✓ Database is already running"
    else
        # Container exists but not running, start it
        docker start conversational-bot-db
        echo "✓ Database started successfully"
    fi
else
    # Container doesn't exist, create and start it using docker-compose
    echo "Creating and starting database container..."
    docker-compose up -d
    
    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    sleep 3
    
    # Initialize database with schema
    echo "Initializing database schema..."
    docker exec conversational-bot-db psql -U postgres -c "CREATE DATABASE conversational_bot;" 2>/dev/null || echo "Database already exists"
    docker exec -i conversational-bot-db psql -U postgres -d conversational_bot < init.sql
    
    echo "✓ Database created and initialized successfully"
fi

# Show connection info
echo ""
echo "Database Connection Info:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: conversational_bot"
echo "  User: postgres"
echo "  Password: postgres"
echo ""
echo "To connect: psql -h localhost -U postgres -d conversational_bot"
