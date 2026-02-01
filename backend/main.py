from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from datetime import datetime
import os

from database import get_db, init_db, UseCaseDB, DocumentDB, DocumentChunkDB, AsyncSessionLocal, ConversationDB, MessageDB
from document_processor import save_upload_file, extract_text_from_file, chunk_text
from embeddings import get_embedding
from agents.base_agent import BaseAgent, ChatMessage
from agents.squad_navigator_agent import SquadNavigatorAgent

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

class ConversationListItem(BaseModel):
    id: int
    title: str
    updatedAt: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: cleanup if needed

app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    history_result = await db.execute(
        select(MessageDB)
        .where(MessageDB.conversation_id == conversation_id)
        .order_by(MessageDB.created_at)
    )
    message_records = history_result.scalars().all()
    
    chat_history = [
        ChatMessage(role=msg.role, content=msg.content, timestamp=msg.created_at.isoformat())
        for msg in message_records
    ]
    
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
    
    return ChatResponse(
        conversationId=conversation_id,
        message=response.message,
        role="assistant",
        timestamp=assistant_message.created_at.isoformat()
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
