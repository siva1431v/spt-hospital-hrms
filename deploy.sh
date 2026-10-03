#!/usr/bin/env bash
set -euo pipefail

echo "══════════════════════════════════════════════"
echo "  SPT Hospital HRMS — Production Deployment"
echo "══════════════════════════════════════════════"
echo ""

# Check .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Copy the template first:"
    echo "   cp .env.production.example .env"
    echo "   Then edit .env with your actual values."
    exit 1
fi

# Source .env for variable access
set -a
source .env
set +a

# Validate required variables
for var in DOMAIN POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB JWT_SECRET; do
    if [ -z "${!var:-}" ]; then
        echo "❌ Required variable $var is not set in .env"
        exit 1
    fi
done

echo "✓ Configuration validated"
echo "  Domain: $DOMAIN"
echo "  Database: $POSTGRES_DB"
echo ""

# Build and start services
echo "► Building Docker images..."
docker compose -f docker-compose.prod.yml build

echo ""
echo "► Starting services..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "► Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
    if docker compose -f docker-compose.prod.yml exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "❌ PostgreSQL failed to start within 30 seconds"
        docker compose -f docker-compose.prod.yml logs postgres
        exit 1
    fi
    sleep 1
done

echo ""
echo "► Waiting for backend to initialize..."
for i in $(seq 1 60); do
    if docker compose -f docker-compose.prod.yml exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ Backend is healthy"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "⚠ Backend health check timed out (may still be starting)"
    fi
    sleep 2
done

echo ""
echo "══════════════════════════════════════════════"
echo "  ✅ Deployment Complete!"
echo "══════════════════════════════════════════════"
echo ""
echo "  🌐 App:     https://$DOMAIN"
echo "  🔧 API:     https://$DOMAIN/api/v1"
echo "  ❤️  Health:  https://$DOMAIN/health"
echo ""
echo "  📋 View logs:    docker compose -f docker-compose.prod.yml logs -f"
echo "  🔄 Restart:      docker compose -f docker-compose.prod.yml restart"
echo "  ⬇️  Stop:         docker compose -f docker-compose.prod.yml down"
echo ""
echo "  Default login: admin / Admin@123"
echo "  ⚠️  CHANGE THE ADMIN PASSWORD IMMEDIATELY!"
echo ""
