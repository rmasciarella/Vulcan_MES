#!/bin/bash

# Script to generate TypeScript API client from FastAPI OpenAPI spec

set -e

echo "🔄 Generating TypeScript API client from FastAPI OpenAPI spec..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if backend is running
if ! curl -s http://localhost:8000/openapi.json > /dev/null; then
    echo -e "${YELLOW}⚠️  Backend is not running. Starting it now...${NC}"
    
    # Start backend in background
    cd apps/backend
    uv run fastapi dev app/main.py &
    BACKEND_PID=$!
    
    # Wait for backend to be ready
    echo "Waiting for backend to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/openapi.json > /dev/null; then
            echo -e "${GREEN}✅ Backend is ready${NC}"
            break
        fi
        sleep 1
    done
    
    if ! curl -s http://localhost:8000/openapi.json > /dev/null; then
        echo -e "${RED}❌ Failed to start backend${NC}"
        exit 1
    fi
    
    cd ../..
fi

# Create directory for generated client
mkdir -p apps/frontend/src/client

# Download OpenAPI spec
echo "📥 Downloading OpenAPI spec..."
curl -s http://localhost:8000/openapi.json > /tmp/openapi.json

# Check if openapi-typescript-codegen is installed
if ! command -v openapi &> /dev/null; then
    echo "📦 Installing openapi-typescript-codegen..."
    npm install -g openapi-typescript-codegen
fi

# Generate TypeScript client
echo "🏗️  Generating TypeScript client..."
openapi \
    --input /tmp/openapi.json \
    --output apps/frontend/src/client \
    --client axios \
    --name VulcanAPIClient \
    --useOptions \
    --useUnionTypes

# Alternative using openapi-ts (if preferred)
# npx openapi-ts generate \
#     --input http://localhost:8000/openapi.json \
#     --output apps/frontend/src/client \
#     --client axios

# Create index file for easier imports
cat > apps/frontend/src/client/index.ts << 'EOF'
/**
 * Auto-generated API client from FastAPI OpenAPI spec
 * Generated on: $(date)
 */

export * from './services';
export * from './models';
export { VulcanAPIClient } from './VulcanAPIClient';

// Re-export with simpler names
export { VulcanAPIClient as ApiClient } from './VulcanAPIClient';

// Create default instance
import { VulcanAPIClient } from './VulcanAPIClient';

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = new VulcanAPIClient({
  BASE: apiUrl,
  WITH_CREDENTIALS: true,
  HEADERS: {
    'Content-Type': 'application/json',
  },
});

// Helper function to set auth token
export const setAuthToken = (token: string) => {
  api.request.config.HEADERS = {
    ...api.request.config.HEADERS,
    Authorization: `Bearer ${token}`,
  };
};

// Helper function to clear auth token
export const clearAuthToken = () => {
  delete api.request.config.HEADERS?.Authorization;
};
EOF

# Create a hook for using the API client in React components
cat > apps/frontend/src/hooks/useApi.ts << 'EOF'
import { useEffect } from 'react';
import { api, setAuthToken, clearAuthToken } from '@/client';
import { useAuth } from './useAuth';

export function useApi() {
  const { token } = useAuth();

  useEffect(() => {
    if (token) {
      setAuthToken(token);
    } else {
      clearAuthToken();
    }
  }, [token]);

  return api;
}
EOF

echo -e "${GREEN}✅ API client generated successfully!${NC}"
echo "📁 Generated files in: apps/frontend/src/client/"

# Kill backend if we started it
if [ ! -z "$BACKEND_PID" ]; then
    echo "Stopping backend..."
    kill $BACKEND_PID 2>/dev/null || true
fi

echo -e "${GREEN}✨ Done! You can now import the API client in your React components:${NC}"
echo ""
echo "  import { api } from '@/client';"
echo "  // or"
echo "  import { useApi } from '@/hooks/useApi';"
echo ""