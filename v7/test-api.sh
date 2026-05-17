#!/bin/bash

# Test script to verify the API endpoint

echo "=== Stock Debate Advisor API Endpoint Test ==="
echo ""

# Test 1: Check health endpoint
echo "Test 1: Health Check"
curl -s http://localhost:8000/health | python -m json.tool || echo "❌ Health check failed - service may not be running"
echo ""

# Test 2: Test debate/start endpoint with correct payload
echo "Test 2: Start Debate Endpoint"
curl -s -X POST http://localhost:8000/api/v1/debate/start \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "timeframe": "3 months",
    "min_rounds": 1,
    "max_rounds": 3
  }' | python -m json.tool || echo "❌ Debate start failed"
echo ""

# Test 3: Test with wrong payload (old format)
echo "Test 3: Debug - Wrong Payload Format (should fail)"
curl -s -X POST http://localhost:8000/api/v1/debate/start \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "rounds": 3}' | python -m json.tool || echo "Expected to fail with wrong payload"
echo ""

echo "=== Test Complete ==="
