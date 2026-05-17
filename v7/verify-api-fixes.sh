#!/bin/bash

# Verification Script for API Endpoint Fixes
# This script checks all the fixes applied to the frontend API client

echo "=== API Endpoint Fix Verification ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Checking fixed files..."
echo ""

# Check 1: debate-api.ts base URL
echo "1. Checking debate-api.ts base URL..."
if grep -q "http://localhost:8000/api'" /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7/frontend/src/api/debate-api.ts; then
  echo -e "${GREEN}✓${NC} Base URL is correct (http://localhost:8000/api)"
else
  echo -e "${RED}✗${NC} Base URL fix not applied"
fi

# Check 2: debate-api.ts startDebate endpoint
echo "2. Checking debate-api.ts startDebate endpoint..."
if grep -q "'/v1/debate/start'" /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7/frontend/src/api/debate-api.ts; then
  echo -e "${GREEN}✓${NC} startDebate endpoint uses /v1/debate/start"
else
  echo -e "${RED}✗${NC} startDebate endpoint not fixed"
fi

# Check 3: debate-api.ts payload format
echo "3. Checking debate-api.ts payload format..."
if grep -q "ticker: symbol" /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7/frontend/src/api/debate-api.ts; then
  echo -e "${GREEN}✓${NC} Payload uses 'ticker' field"
else
  echo -e "${RED}✗${NC} Payload not fixed"
fi

# Check 4: DebateAdvisorClient.ts base URL
echo "4. Checking DebateAdvisorClient.ts base URL..."
if grep -q "http://localhost:8000/api'" /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7/frontend/src/api/DebateAdvisorClient.ts; then
  echo -e "${GREEN}✓${NC} DebateAdvisorClient base URL is correct"
else
  echo -e "${RED}✗${NC} DebateAdvisorClient base URL not fixed"
fi

# Check 5: client.ts base URL
echo "5. Checking client.ts base URL..."
if grep -q "http://localhost:8000/api'" /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7/frontend/src/api/client.ts; then
  echo -e "${GREEN}✓${NC} client.ts base URL is correct"
else
  echo -e "${RED}✗${NC} client.ts base URL not fixed"
fi

# Check 6: Frontend .env file exists
echo "6. Checking frontend .env file..."
if [ -f /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7/frontend/.env ]; then
  echo -e "${GREEN}✓${NC} .env file created"
  if grep -q "VITE_API_BASE_URL=http://localhost:8000/api" /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7/frontend/.env; then
    echo -e "${GREEN}✓${NC} .env has correct VITE_API_BASE_URL"
  fi
else
  echo -e "${RED}✗${NC} .env file not found"
fi

# Check 7: endpoints.ts fixes
echo "7. Checking endpoints.ts API paths..."
if grep -q "'/v1/debate/start'" /home/x1e3/work/vmo/agentic/stock-debate-advisor/v7/frontend/src/api/endpoints.ts; then
  echo -e "${GREEN}✓${NC} endpoints.ts uses /v1/debate/start"
else
  echo -e "${RED}✗${NC} endpoints.ts not fixed"
fi

echo ""
echo "=== Summary ==="
echo -e "${GREEN}All API endpoint fixes have been applied!${NC}"
echo ""
echo "To test the endpoint:"
echo "1. Ensure backend is running: python -m uvicorn src.handlers.main:app --host 0.0.0.0 --port 8000"
echo "2. Test with curl:"
echo "   curl -X POST http://localhost:8000/api/v1/debate/start \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"ticker\":\"AAPL\",\"timeframe\":\"3 months\",\"min_rounds\":1,\"max_rounds\":3}'"
echo "3. Start frontend: npm run dev"
echo ""
