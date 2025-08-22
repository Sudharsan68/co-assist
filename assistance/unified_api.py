import sys
if sys.platform.startswith("win"):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# unified_api.py

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uvicorn
import os
import sys
import asyncio
import logging
import tempfile
from dotenv import load_dotenv

# =========================
# Environment
# =========================
load_dotenv()

# Ensure project root on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# =========================
# Project imports (safe at import-time)
# =========================
from agent_with_crewAI.search_service import SearchService
from pdf.retriever.app import app as pdf_app

# Gmail agent + parser (safe)
from gmail_automation.utils.env_loader import load_env as load_gmail_env
from gmail_automation.agents.gmail_agent import GmailAgent
from gmail_automation.main import parse_email_json  # parsing only (no browser here)

# PDF processing imports
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from pdf.retriever.llm import token
from pdf.retriever.retreive import qdrant

# =========================
# Logger setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =========================
# FastAPI app
# =========================
app = FastAPI(
    title="Unified Project API",
    description="Single FastAPI endpoint to access all project functionalities",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Models (Pydantic v2)
# =========================
class SearchRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    max_results: int = 5
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "latest updates on Python 3.13",
                "context": {"domain": "dev"},
                "max_results": 5
            }
        }
    )

class EmailRequest(BaseModel):
    to: List[str]
    subject: str
    body: str
    cc: Optional[List[str]] = Field(default_factory=list)
    bcc: Optional[List[str]] = Field(default_factory=list)
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "to": ["someone@example.com"],
                "subject": "Weekly Status Update",
                "body": "Hi team, here is the weekly status...",
                "cc": [],
                "bcc": []
            }
        }
    )

class GmailSendRequest(BaseModel):
    task: str
    to: Optional[List[str]] = Field(default_factory=list)
    cc: Optional[List[str]] = Field(default_factory=list)
    bcc: Optional[List[str]] = Field(default_factory=list)
    tone: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task": "Email my professor requesting an extension to Friday; keep it formal.",
                "to": ["professor@university.com"],
                "tone": "formal",
                "cc": [],
                "bcc": []
            }
        }
    )

class PDFSearchRequest(BaseModel):
    question: str
    max_results: int = 5
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What are the key findings from the 2023 annual report?",
                "max_results": 5
            }
        }
    )

# =========================
# Gmail Agent initialization
# =========================
gmail_agent = None
gmail_env = None
gmail_init_error = None

try:
    gmail_env = load_gmail_env()
    groq_key = gmail_env.get("GROQ_API_KEY")
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY missing in environment.")
    gmail_agent = GmailAgent(groq_api_key=groq_key)
except Exception as e:
    gmail_init_error = str(e)
    print(f"[WARN] Gmail agent initialization failed: {gmail_init_error}", file=sys.stderr, flush=True)

# =========================
# Async Gmail automation helper
# =========================
async def _send_email_async(email_data: Dict[str, Any], env: Dict[str, Any]) -> None:
    """
    Async version of email sending using Playwright's async API.
    Runs directly in the event loop without threading.
    """
    from playwright.async_api import async_playwright
    from gmail_automation.main_async import login as login_async, send_email as send_email_async
    
    try:
        print("[PW] Launching async Chrome context…", file=sys.stderr, flush=True)
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir="C:/Users/Sudharsan/AppData/Local/Google/Chrome/User Data/GmailAutomation",
                channel="chrome",
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            )
            
            page = await browser.new_page()
            print("[PW] Logging into Gmail (using existing profile)…", file=sys.stderr, flush=True)
            await login_async(page, env)
            
            print("[PW] Sending email…", file=sys.stderr, flush=True)
            await send_email_async(page, email_data)
            print("[PW] Email sent successfully.", file=sys.stderr, flush=True)
            
            await browser.close()
            
    except Exception as e:
        print(f"[PW][ERROR] Async send failed: {e}", file=sys.stderr, flush=True)
        raise

# =========================
# Root & Health
# =========================
@app.get("/", tags=["root"])
async def root():
    return {
        "message": "Unified Project API - Access all projects from one endpoint",
        "endpoints": {
            "agent": "/agent/search",
            "gmail": "/gmail/send",
            "pdf": ["/pdf/upload", "/pdf/search"],
            "health": "/health",
            "models": "/v1/models",
            "dashboard": "/dashboard"
        }
    }

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "Unified Project API",
        "gmail_agent_initialized": gmail_agent is not None,
        "gmail_init_error": gmail_init_error
    }

# =========================
# Agent: Search
# =========================
@app.post("/agent/search", tags=["agent"])
async def agent_search(request: SearchRequest):
    try:
        result = SearchService.search_web(
            query=request.query,
            context=request.context,
            max_results=request.max_results
        )
        if result.get("success"):
            return result
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# Gmail: One-step LLM → Send
# =========================
@app.post("/gmail/send", tags=["gmail"])
async def gmail_send(request: GmailSendRequest):
    """
    - Accepts natural-language task (+ optional tone & recipients)
    - Uses LLM to generate subject/body
    - Validates structure
    - Offloads Playwright sync UI automation to a worker thread
    """
    if gmail_agent is None or gmail_env is None:
        raise HTTPException(
            status_code=503,
            detail=f"Gmail service not available. {gmail_init_error or 'Check configuration.'}"
        )

    try:
        # 1) Use LLM to convert task → structured email (subject/body)
        instructions = gmail_agent.parse_task(request.task, tone_hint=request.tone)

        # 2) Merge recipients from request (override/fill)
        if request.to:
            instructions["to"] = request.to
        if request.cc:
            instructions["cc"] = request.cc
        if request.bcc:
            instructions["bcc"] = request.bcc

        # 3) Validate final structure
        email_data = parse_email_json(instructions)
        if not email_data.get("to"):
            raise ValueError("No recipient found after parsing/merge.")

        # 4) Log payload (to server console)
        print("[GMAIL] Prepared email_data:", email_data, file=sys.stderr, flush=True)

        # 5) Async Playwright automation (no threading needed)
        try:
            print("[GMAIL] Starting async Playwright automation…", file=sys.stderr, flush=True)
            await _send_email_async(email_data, gmail_env)
            print("[GMAIL] Async Playwright completed successfully.", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[GMAIL][ERROR] Async send failed: {e}", file=sys.stderr, flush=True)
            raise HTTPException(status_code=500, detail=f"Gmail send failed: {str(e)}")

        return {
            "success": True,
            "message": "✅ Email sent successfully",
            "email_preview": email_data
        }

    except HTTPException:
        raise
    except Exception as e:
        # Any earlier error (LLM parse, validation, etc.)
        raise HTTPException(status_code=500, detail=f"Gmail send failed: {str(e)}")

# =========================
# Gmail: Placeholder search
# =========================
@app.post("/gmail/search", tags=["gmail"])
async def gmail_search(query: str, max_results: int = 10):
    try:
        return {"success": True, "results": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# PDF
# =========================
@app.post('/api/upload')
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    temp_file_path = None
    try:
        logger.info(f"Processing upload: {file.filename}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        logger.info("Loading PDF document...")
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()

        logger.info("Splitting document into chunks...")
        text_splitter = CharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separator="\n"
        )
        chunks = text_splitter.split_documents(documents)

        logger.info(f"Adding {len(chunks)} chunks to vector store...")
        qdrant.add_documents(chunks)

        logger.info(f"Successfully processed {file.filename}")
        return {
            "success": True,
            "message": f"Successfully uploaded and processed {file.filename}",
            "filename": file.filename,
            "chunks_added": len(chunks),
        }

    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@app.post('/api/search')
async def search_documents(query: PDFSearchRequest):
    try:
        question = query.question

        if not question:
            raise HTTPException(status_code=400, detail='Question is required')

        logger.info(f"Processing search query: {question[:50]}...")

        # Search for relevant documents
        logger.info("Searching for relevant document chunks...")
        chunks = qdrant.similarity_search(question, k=5)

        # Create context from chunks
        context = "\n".join([chunk.page_content for chunk in chunks])
        logger.info(f"Found {len(chunks)} relevant chunks")

        # Generate response using your LLM
        logger.info("Generating AI response...")
        response = token(question, "x-ai/grok-2-vision-1212", context)

        logger.info("Search completed successfully")
        return {
            'response': response,
            'context': context,
            'chunks_found': len(chunks)
        }
    except Exception as e:
        logger.error(f"Error in search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

# =========================
# Compatibility endpoint
# =========================
@app.get("/v1/models", tags=["compat"])
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "unified-model", "object": "model", "created": 1700000000, "owned_by": "unified-project-api", "permission": []},
            {"id": "crewai-agent", "object": "model", "created": 1700000000, "owned_by": "unified-project-api", "permission": []},
            {"id": "gmail-automation", "object": "model", "created": 1700000000, "owned_by": "unified-project-api", "permission": []},
            {"id": "pdf-processor", "object": "model", "created": 1700000000, "owned_by": "unified-project-api", "permission": []},
        ]
    }

# =========================
# Dashboard
# =========================
@app.get("/dashboard", tags=["dashboard"])
async def get_dashboard():
    return {
        "available_services": {
            "agent": {"description": "CrewAI web search agent", "endpoints": ["/agent/search"]},
            "gmail": {"description": "Gmail automation service (LLM → send)", "endpoints": ["/gmail/send"]},
            "pdf": {"description": "PDF processing and Q&A", "endpoints": ["/pdf/upload", "/pdf/search"]},
        }
    }

# =========================
# Entrypoint
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
