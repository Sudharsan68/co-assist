import uvicorn
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from pdf.retriever.llm import token
from pydantic import BaseModel, Field, ConfigDict
import os
from dotenv import load_dotenv
import tempfile
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Global variable for qdrant
qdrant = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        global qdrant
        logger.info("Initializing embeddings model...")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        url = "https://9629e0dd-b11d-428c-a3d9-a5c7423e46cf.us-east4-0.gcp.cloud.qdrant.io"
        api_key = os.environ.get("QDRANT_API_KEY")
        
        if not api_key:
            logger.error("QDRANT_API_KEY environment variable not set!")
            raise ValueError("QDRANT_API_KEY environment variable not set!")

        logger.info("Connecting to Qdrant...")
        qdrant = QdrantVectorStore.from_existing_collection(
            embedding=embeddings,
            collection_name="my_documents",  # Make sure this matches your upload.py
            url=url,
            api_key=api_key,
        )
        logger.info("✅ Successfully connected to Qdrant!")
    except Exception as e:
        logger.error(f"❌ Error connecting to Qdrant: {e}")
        logger.error("Please check your internet connection and API keys.")
        raise e
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="PDF Summarizer API",
    description="AI-powered PDF document processing and summarization API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for production
origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
    "http://172.20.10.5:8080",  # Your frontend IP
    "http://172.20.10.5:3000",  # Alternative frontend port
    # Add your production frontend URL here
    # "https://your-frontend-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

class SearchQuery(BaseModel):
    question: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What are the key findings from the 2023 annual report?"
            }
        }
    )

# Initialize embeddings and Qdrant
# @app.on_event("startup")
# async def startup_event():
#     try:
#         global qdrant
#         logger.info("Initializing embeddings model...")
#         embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
#         
#         url = "https://9629e0dd-b11d-428c-a3d9-a5c7423e46cf.us-east4-0.gcp.cloud.qdrant.io"
#         api_key = os.environ.get("QDRANT_API_KEY")
#         
#         if not api_key:
#             logger.error("QDRANT_API_KEY environment variable not set!")
#             raise ValueError("QDRANT_API_KEY environment variable not set!")

#         logger.info("Connecting to Qdrant...")
#         qdrant = QdrantVectorStore.from_existing_collection(
#             embedding=embeddings,
#             collection_name="my_documents",  # Make sure this matches your upload.py
#             url=url,
#             api_key=api_key,
#         )
#         logger.info("✅ Successfully connected to Qdrant!")
#     except Exception as e:
#         logger.error(f"❌ Error connecting to Qdrant: {e}")
#         logger.error("Please check your internet connection and API keys.")
#         raise e

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
async def search_documents(query: SearchQuery):
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

@app.get('/api/health')
def health_check():
    try:
        # Test Qdrant connection
        qdrant.client.get_collections()
        return {
            'status': 'healthy',
            'message': 'API is running',
            'qdrant': 'connected',
            'timestamp': '2024-01-01T00:00:00Z'
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'message': 'API is running but Qdrant connection failed',
            'qdrant': 'disconnected',
            'error': str(e),
            'timestamp': '2024-01-01T00:00:00Z'
        }

@app.get('/')
def root():
    return {'message': 'PDF Chat API is running'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)
