#!/usr/bin/env python3
"""
Fixed Windows-compatible runner for Unified Project API
"""

import sys
import os

# Set Windows event loop policy BEFORE any imports
if sys.platform.startswith("win"):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Now import everything else
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    
    print("🚀 Starting Unified Project API (Windows Fixed)...")
    print(f"📡 Server running at http://{host}:{port}")
    print("📋 Available endpoints:")
    print("   - GET  /           - API overview")
    print("   - GET  /health     - Health check")
    print("   - GET  /dashboard  - Service overview")
    print("   - POST /agent/search - CrewAI web search")
    print("   - POST /gmail/send - Gmail automation")
    print("   - POST /pdf/search - PDF Q&A")
    
    # Run without reload for Windows compatibility
    uvicorn.run("unified_api:app", host=host, port=port, reload=False)
