from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from datetime import datetime
import os
import time
import logging

from clients.database import get_db, init_db, UseCaseDB, DocumentDB, DocumentChunkDB, AsyncSessionLocal, ConversationDB, MessageDB
from clients.redis_client import redis_client
from clients.elasticsearch_client import es_client
from document_processor import save_upload_file, extract_text_from_file, chunk_text
from embeddings import get_embedding
from agents.base_agent import BaseAgent, ChatMessage
from agents.squad_navigator_agent import SquadNavigatorAgent
from logger_config import setup_logging, get_uvicorn_log_config

# Initialize logging
logger = setup_logging()

class UseCase(BaseModel):
    id: int
    name: str
    uriContext: str

    class Config:
        from_attributes = True

class UseCaseDetail(BaseModel):
    id: int
    name: str
    uriContext: str
    title: str
    description: str
    details: str

    class Config:
        from_attributes = True

class Document(BaseModel):
    id: int
    filename: str
    file_size: int
    uploaded_at: str
    status: str

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    message: str
    conversationId: int | None = None

class ChatResponse(BaseModel):
    conversationId: int
    message: str
    role: str
    timestamp: str
    title: str = None

class ConversationListItem(BaseModel):
    id: int
    title: str
    updatedAt: str

class ConversationMessage(BaseModel):
    id: int
    role: str
    content: str
    timestamp: str

class ConversationDetail(BaseModel):
    conversationId: int
    title: str
    messages: List[ConversationMessage]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    logger.info("Starting application...")
    await init_db()
    
    # Test Redis connection
    if redis_client.ping():
        logger.info("✓ Redis connected")
        print("✓ Redis connected")
    else:
        logger.warning("⚠ Redis connection failed - caching disabled")
        print("⚠ Redis connection failed - caching disabled")
    
    # Test Elasticsearch connection
    if es_client.ping():
        logger.info("✓ Elasticsearch connected")
        print("✓ Elasticsearch connected")
    else:
        logger.warning("⚠ Elasticsearch connection failed - search features disabled")
        print("⚠ Elasticsearch connection failed - search features disabled")
    
    logger.info("Application startup complete")
    yield
    
    # Shutdown: cleanup connections
    logger.info("Shutting down application...")
    redis_client.close()
    es_client.close()
    logger.info("Application shutdown complete")

app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware using Redis"""
    # Skip rate limiting for health checks and static files
    if request.url.path in ["/", "/health", "/api/health"]:
        return await call_next(request)
    
    # Get client identifier (IP address for now, could be user ID with auth)
    client_id = request.client.host
    endpoint = request.url.path
    
    # Check rate limit
    allowed, remaining = redis_client.check_rate_limit(client_id, endpoint)
    
    if not allowed:
        return Response(
            content='{"detail": "Rate limit exceeded. Please try again later."}',
            status_code=429,
            media_type="application/json",
            headers={
                "X-RateLimit-Limit": str(redis_client.rate_limit_rpm),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(60 - (int(time.time()) % 60))
            }
        )
    
    # Process request
    response = await call_next(request)
    
    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(redis_client.rate_limit_rpm)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(60 - (int(time.time()) % 60))
    
    return response

@app.get("/")
def read_root():
    return {"message": "Welcome to Conversational Agentic Bot API"}

@app.get("/api/use-cases", response_model=List[UseCase])
async def get_use_cases(db: AsyncSession = Depends(get_db)):
    """
    Returns the list of available use cases from database
    """
    result = await db.execute(select(UseCaseDB))
    use_cases = result.scalars().all()
    
    return [
        UseCase(
            id=uc.id,
            name=uc.name,
            uriContext=uc.uri_context
        )
        for uc in use_cases
    ]

@app.get("/api/use-cases/{uri_context}", response_model=UseCaseDetail)
async def get_use_case_details(uri_context: str, db: AsyncSession = Depends(get_db)):
    """
    Returns detailed information about a specific use case from database
    """
    result = await db.execute(
        select(UseCaseDB).where(UseCaseDB.uri_context == uri_context)
    )
    use_case = result.scalar_one_or_none()
    
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    return UseCaseDetail(
        id=use_case.id,
        name=use_case.name,
        uriContext=use_case.uri_context,
        title=use_case.title,
        description=use_case.description,
        details=use_case.details
    )

async def process_document_background(document_id: int, file_path: str, use_case_uri: str):
    """
    Background task to process document: extract text, chunk, embed, and store
    """
    async with AsyncSessionLocal() as db:
        try:
            # Extract text from document
            text = extract_text_from_file(file_path)
            
            # Chunk the text
            chunks = chunk_text(text)
            
            # Generate embeddings and store in database
            chunk_records = []
            
            for idx, chunk in enumerate(chunks):
                # Generate embedding
                embedding = get_embedding(chunk)
                
                # Create chunk record for PostgreSQL database with embedding
                chunk_record = DocumentChunkDB(
                    document_id=document_id,
                    chunk_index=idx,
                    content=chunk,
                    embedding=embedding  # Store embedding directly in PostgreSQL
                )
                chunk_records.append(chunk_record)
            
            # Store chunk records in PostgreSQL database
            for chunk_record in chunk_records:
                db.add(chunk_record)
            
            # Update document status
            result = await db.execute(
                select(DocumentDB).where(DocumentDB.id == document_id)
            )
            document = result.scalar_one()
            document.status = "completed"
            
            await db.commit()
            print(f"✓ Document {document_id} processed successfully with {len(chunks)} chunks")
            
        except Exception as e:
            # Update document status to failed
            result = await db.execute(
                select(DocumentDB).where(DocumentDB.id == document_id)
            )
            document = result.scalar_one_or_none()
            if document:
                document.status = "failed"
                await db.commit()
            print(f"✗ Error processing document {document_id}: {str(e)}")
            raise

@app.post("/api/use-cases/{uri_context}/upload")
async def upload_document(
    uri_context: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document for a specific use case
    """
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    # Get use case
    result = await db.execute(
        select(UseCaseDB).where(UseCaseDB.uri_context == uri_context)
    )
    use_case = result.scalar_one_or_none()
    
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Validate file type
    allowed_extensions = ['.pdf', '.txt', '.md']
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Save file
    file_path, file_size = await save_upload_file(file, use_case.id)
    
    # Create document record
    document = DocumentDB(
        use_case_id=use_case.id,
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        status="processing"
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Process document in background
    background_tasks.add_task(
        process_document_background,
        document.id,
        file_path,
        uri_context
    )
    
    return {
        "message": "File uploaded successfully",
        "document_id": document.id,
        "filename": file.filename,
        "status": "processing"
    }

@app.get("/api/use-cases/{uri_context}/documents", response_model=List[Document])
async def get_documents(uri_context: str, db: AsyncSession = Depends(get_db)):
    """
    Get all documents for a specific use case
    """
    # Get use case
    result = await db.execute(
        select(UseCaseDB).where(UseCaseDB.uri_context == uri_context)
    )
    use_case = result.scalar_one_or_none()
    
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get documents
    result = await db.execute(
        select(DocumentDB).where(DocumentDB.use_case_id == use_case.id)
    )
    documents = result.scalars().all()
    
    return [
        Document(
            id=doc.id,
            filename=doc.filename,
            file_size=doc.file_size,
            uploaded_at=doc.uploaded_at.isoformat(),
            status=doc.status
        )
        for doc in documents
    ]

@app.delete("/api/use-cases/{uri_context}/documents/{document_id}")
async def delete_document(
    uri_context: str,
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a document
    """
    # Get use case
    result = await db.execute(
        select(UseCaseDB).where(UseCaseDB.uri_context == uri_context)
    )
    use_case = result.scalar_one_or_none()
    
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get document
    result = await db.execute(
        select(DocumentDB).where(
            DocumentDB.id == document_id,
            DocumentDB.use_case_id == use_case.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete associated chunks first
    await db.execute(
        select(DocumentChunkDB).where(DocumentChunkDB.document_id == document_id)
    )
    chunks_result = await db.execute(
        select(DocumentChunkDB).where(DocumentChunkDB.document_id == document_id)
    )
    chunks = chunks_result.scalars().all()
    
    for chunk in chunks:
        await db.delete(chunk)
    
    # Delete the document file from filesystem
    import os
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
    
    # Delete document from database
    await db.delete(document)
    await db.commit()
    
    return {"message": "Document deleted successfully"}

@app.post("/api/use-cases/{uri_context}/chat", response_model=ChatResponse)
async def chat(
    uri_context: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Chat endpoint for conversational AI
    """
    # Get use case
    result = await db.execute(
        select(UseCaseDB).where(UseCaseDB.uri_context == uri_context)
    )
    use_case = result.scalar_one_or_none()
    
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get or create conversation
    conversation_id = request.conversationId
    if conversation_id:
        # Load existing conversation
        conv_result = await db.execute(
            select(ConversationDB).where(ConversationDB.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        # Create new conversation
        conversation = ConversationDB(
            use_case_id=use_case.id,
            title=request.message[:50] + "..." if len(request.message) > 50 else request.message
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        conversation_id = conversation.id
    
    # Load conversation history
    # Try to get from Redis cache first
    cached_messages = redis_client.get_cached_conversation(conversation_id)
    
    if cached_messages:
        message_records = []
        chat_history = [
            ChatMessage(role=msg["role"], content=msg["content"], timestamp=msg["timestamp"])
            for msg in cached_messages
        ]
        # Note: message_records will be empty from cache, we'll load from DB for state
        history_result = await db.execute(
            select(MessageDB)
            .where(MessageDB.conversation_id == conversation_id)
            .order_by(MessageDB.created_at)
        )
        message_records = history_result.scalars().all()
    else:
        # Load from database
        history_result = await db.execute(
            select(MessageDB)
            .where(MessageDB.conversation_id == conversation_id)
            .order_by(MessageDB.created_at)
        )
        message_records = history_result.scalars().all()
        
        chat_history = [
            ChatMessage(role=msg.role, content=msg.content, timestamp=msg.created_at.isoformat() + 'Z' if msg.created_at else None)
            for msg in message_records
        ]
        
        # Cache the conversation history
        cache_data = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat() + 'Z' if msg.created_at else None
            }
            for msg in message_records
        ]
        redis_client.cache_conversation(conversation_id, cache_data)
    
    # Load conversation state from last assistant message
    conversation_state = None
    for msg in reversed(message_records):
        if msg.role == "assistant" and msg.msg_metadata:
            conversation_state = msg.msg_metadata.get("conversation_state")
            if conversation_state:
                break
    
    # Save user message
    user_message = MessageDB(
        conversation_id=conversation_id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)
    
    # Index user message in Elasticsearch (async, non-blocking)
    try:
        es_client.index_message(
            message_id=user_message.id,
            conversation_id=conversation_id,
            use_case_id=use_case.id,
            role="user",
            content=request.message,
            created_at=user_message.created_at
        )
    except Exception as e:
        print(f"Error indexing user message in Elasticsearch: {e}")
    
    # Create agent based on use case type
    if use_case.uri_context == "squad-navigator":
        agent = SquadNavigatorAgent(use_case_id=use_case.id, use_case_name=use_case.name)
    else:
        agent = BaseAgent(use_case_id=use_case.id, use_case_name=use_case.name)
    
    response = await agent.process_message(
        user_message=request.message,
        chat_history=chat_history,
        db=db,
        conversation_state=conversation_state
    )
    
    # Save assistant message
    assistant_message = MessageDB(
        conversation_id=conversation_id,
        role="assistant",
        content=response.message,
        msg_metadata=response.metadata
    )
    db.add(assistant_message)
    
    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(assistant_message)
    
    # Index assistant message in Elasticsearch
    try:
        es_client.index_message(
            message_id=assistant_message.id,
            conversation_id=conversation_id,
            use_case_id=use_case.id,
            role="assistant",
            content=response.message,
            created_at=assistant_message.created_at,
            metadata=response.metadata
        )
    except Exception as e:
        print(f"Error indexing assistant message in Elasticsearch: {e}")
    
    # Invalidate conversation cache since we added new messages
    redis_client.invalidate_conversation(conversation_id)
    
    # Generate title after 4 messages (2 user + 2 assistant)
    conversation_title = conversation.title
    message_count = len(message_records) + 2  # existing + current user + assistant
    if message_count >= 4:
        # Generate or regenerate title based on first two user messages
        try:
            from langchain_openai import ChatOpenAI
            from langchain.schema import SystemMessage, HumanMessage
            import os
            
            # Get first two user messages
            user_messages = [msg for msg in message_records if msg.role == "user"]
            user_messages.append(user_message)  # Add current user message
            
            if len(user_messages) >= 2:
                llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.3)
                title_response = await llm.ainvoke([
                    SystemMessage(content="Generate a short, concise title (max 6 words) for a conversation based on these user messages. Only return the title, nothing else."),
                    HumanMessage(content=f"Message 1: {user_messages[0].content}\\nMessage 2: {user_messages[1].content}")
                ])
                conversation.title = title_response.content.strip()
                conversation_title = conversation.title
                await db.commit()
                
                # Index conversation in Elasticsearch with title
                try:
                    es_client.index_conversation(
                        conversation_id=conversation_id,
                        use_case_id=use_case.id,
                        title=conversation_title,
                        created_at=conversation.created_at,
                        updated_at=conversation.updated_at,
                        message_count=message_count
                    )
                except Exception as e:
                    print(f"Error indexing conversation in Elasticsearch: {e}")
        except Exception as e:
            print(f"Error generating title: {e}")
    
    return ChatResponse(
        conversationId=conversation_id,
        message=response.message,
        role="assistant",
        timestamp=assistant_message.created_at.isoformat() + 'Z',
        title=conversation_title
    )

@app.get("/api/use-cases/{uri_context}/conversations", response_model=List[ConversationListItem])
async def get_conversations(
    uri_context: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of conversations for a use case
    """
    # Get use case
    result = await db.execute(
        select(UseCaseDB).where(UseCaseDB.uri_context == uri_context)
    )
    use_case = result.scalar_one_or_none()
    
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get conversations
    conversations_result = await db.execute(
        select(ConversationDB)
        .where(ConversationDB.use_case_id == use_case.id)
        .order_by(ConversationDB.updated_at.desc())
    )
    conversations = conversations_result.scalars().all()
    
    return [
        ConversationListItem(
            id=conv.id,
            title=conv.title or "New Conversation",
            updatedAt=conv.updated_at.isoformat()
        )
        for conv in conversations
    ]

@app.get("/api/use-cases/{uri_context}/last-conversation", response_model=ConversationDetail | None)
async def get_last_conversation(
    uri_context: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the last conversation for a use case with all its messages
    """
    # Get use case
    result = await db.execute(
        select(UseCaseDB).where(UseCaseDB.uri_context == uri_context)
    )
    use_case = result.scalar_one_or_none()
    
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get last conversation
    conversation_result = await db.execute(
        select(ConversationDB)
        .where(ConversationDB.use_case_id == use_case.id)
        .order_by(ConversationDB.updated_at.desc())
        .limit(1)
    )
    conversation = conversation_result.scalar_one_or_none()
    
    if not conversation:
        return None
    
    # Get messages for this conversation
    messages_result = await db.execute(
        select(MessageDB)
        .where(MessageDB.conversation_id == conversation.id)
        .order_by(MessageDB.created_at)
    )
    messages = messages_result.scalars().all()
    
    return ConversationDetail(
        conversationId=conversation.id,
        title=conversation.title or "",
        messages=[
            ConversationMessage(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                timestamp=msg.created_at.isoformat() + 'Z'
            )
            for msg in messages
        ]
    )

@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_by_id(
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific conversation by ID with all its messages
    """
    # Get conversation
    conversation_result = await db.execute(
        select(ConversationDB).where(ConversationDB.id == conversation_id)
    )
    conversation = conversation_result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get messages for this conversation
    messages_result = await db.execute(
        select(MessageDB)
        .where(MessageDB.conversation_id == conversation.id)
        .order_by(MessageDB.created_at)
    )
    messages = messages_result.scalars().all()
    
    return ConversationDetail(
        conversationId=conversation.id,
        title=conversation.title or "",
        messages=[
            ConversationMessage(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                timestamp=msg.created_at.isoformat() + 'Z'
            )
            for msg in messages
        ]
    )

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a conversation and all its messages
    """
    # Get conversation
    conversation_result = await db.execute(
        select(ConversationDB).where(ConversationDB.id == conversation_id)
    )
    conversation = conversation_result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Delete conversation (messages will be cascade deleted)
    await db.delete(conversation)
    await db.commit()
    
    # Delete from Elasticsearch
    try:
        es_client.delete_conversation(conversation_id)
    except Exception as e:
        print(f"Error deleting conversation from Elasticsearch: {e}")
    
    # Invalidate Redis cache
    redis_client.invalidate_conversation(conversation_id)
    
    return {"message": "Conversation deleted successfully"}


# ============================================
# Search Endpoints
# ============================================

class SearchRequest(BaseModel):
    query: str
    use_case_id: Optional[int] = None
    conversation_id: Optional[int] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    size: int = 20
    from_: int = 0

class SearchResult(BaseModel):
    id: str
    conversation_id: int
    role: str
    content: str
    created_at: str
    score: float
    highlight: Optional[dict] = None

class SearchResponse(BaseModel):
    total: int
    results: List[SearchResult]

@app.post("/api/search/messages", response_model=SearchResponse)
async def search_messages(request: SearchRequest):
    """
    Full-text search across all messages using Elasticsearch
    """
    try:
        results = es_client.search_messages(
            query=request.query,
            use_case_id=request.use_case_id,
            conversation_id=request.conversation_id,
            from_date=request.from_date,
            to_date=request.to_date,
            size=request.size,
            from_=request.from_
        )
        
        return SearchResponse(
            total=results["total"],
            results=[
                SearchResult(
                    id=hit["id"],
                    conversation_id=hit["conversation_id"],
                    role=hit["role"],
                    content=hit["content"],
                    created_at=hit["created_at"],
                    score=hit["score"],
                    highlight=hit.get("highlight")
                )
                for hit in results["hits"]
            ]
        )
    except Exception as e:
        print(f"Search error: {e}")
        return SearchResponse(total=0, results=[])

@app.get("/api/search/conversations/{use_case_id}")
async def search_conversations(use_case_id: int, query: str, size: int = 20):
    """
    Search conversations by title
    """
    try:
        results = es_client.search_conversations(
            query=query,
            use_case_id=use_case_id,
            size=size
        )
        
        return {
            "total": results["total"],
            "conversations": [
                {
                    "id": hit["conversation_id"],
                    "title": hit["title"],
                    "updated_at": hit["updated_at"],
                    "score": hit["score"]
                }
                for hit in results["hits"]
            ]
        }
    except Exception as e:
        print(f"Conversation search error: {e}")
        return {"total": 0, "conversations": []}


# ============================================
# Health & Stats Endpoints
# ============================================

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint with infrastructure status
    """
    redis_status = redis_client.ping()
    es_status = es_client.ping()
    
    return {
        "status": "healthy" if (redis_status and es_status) else "degraded",
        "services": {
            "database": "connected",
            "redis": "connected" if redis_status else "disconnected",
            "elasticsearch": "connected" if es_status else "disconnected"
        }
    }

@app.get("/api/stats")
async def get_infrastructure_stats():
    """
    Get infrastructure statistics for monitoring
    """
    redis_stats = redis_client.get_stats()
    es_stats = es_client.get_stats()
    
    return {
        "redis": redis_stats,
        "elasticsearch": es_stats
    }

@app.get("/api/stats/messages")
async def get_message_stats(use_case_id: Optional[int] = None):
    """
    Get message analytics from Elasticsearch
    """
    try:
        stats = es_client.get_message_stats(use_case_id=use_case_id)
        return stats
    except Exception as e:
        print(f"Error getting message stats: {e}")
        return {"error": str(e)}


    
    return UseCaseDetail(
        id=use_case.id,
        name=use_case.name,
        uriContext=use_case.uri_context,
        title=use_case.title,
        description=use_case.description,
        details=use_case.details
    )

if __name__ == "__main__":
    import uvicorn
    
    # Get uvicorn logging configuration
    log_config = get_uvicorn_log_config()
    
    # Run with logging configuration
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=log_config
    )
