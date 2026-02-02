"""
Base Agent Interface for all use cases
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ChatMessage:
    """Represents a chat message"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[str] = None


@dataclass
class AgentResponse:
    """Response from agent"""
    message: str
    metadata: Optional[Dict[str, Any]] = None


class BaseAgent:
    """
    Base Agent class that provides common functionality for all use cases.
    Each use case can extend this class to implement specific behavior.
    """
    
    def __init__(self, use_case_id: int, use_case_name: str):
        """
        Initialize the base agent
        
        Args:
            use_case_id: The ID of the use case
            use_case_name: The name of the use case
        """
        self.use_case_id = use_case_id
        self.use_case_name = use_case_name
        
        # Initialize LLM based on provider
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        
        if provider == "azure":
            self.llm = AzureChatOpenAI(
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                temperature=0.7
            )
        else:
            self.llm = ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=0.7,
                api_key=os.getenv("OPENAI_API_KEY")
            )
    
    def load_state(self, conversation_state: Optional[dict], chat_history: List[ChatMessage]) -> dict:
        """
        Loads conversation state or initializes a new one.
        
        Args:
            conversation_state: Previous state from database
            chat_history: Message history for context
            
        Returns:
            Initialized or loaded conversation state
        """
        if conversation_state:
            return conversation_state
        
        # Initialize new state for new conversations
        return {
            "stage": "initial_greeting",
            "user_profile": {},
            "context_data": {},
            "conversation_turns": len(chat_history) // 2
        }
    
    def update_state(self, updates: dict) -> dict:
        """
        Updates the current conversation state with new information.
        
        Args:
            updates: Dictionary of state updates to merge
            
        Returns:
            Updated state dictionary
        """
        if not hasattr(self, 'current_state'):
            self.current_state = self.load_state(None, [])
        
        # Deep merge updates into current state
        for key, value in updates.items():
            if key in self.current_state and isinstance(self.current_state[key], dict) and isinstance(value, dict):
                self.current_state[key].update(value)
            else:
                self.current_state[key] = value
        
        return self.current_state
    
    def transition_to_stage(self, new_stage: str, reason: Optional[str] = None) -> dict:
        """
        Transitions conversation to a new stage.
        
        Args:
            new_stage: The stage to transition to
            reason: Optional reason for transition
            
        Returns:
            Updated state with new stage
        """
        old_stage = self.current_state.get("stage", "unknown")
        self.current_state["stage"] = new_stage
        self.current_state["last_transition"] = {
            "from": old_stage,
            "to": new_stage,
            "reason": reason
        }
        return self.current_state
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent.
        Override this method to customize the system prompt for specific use cases.
        
        Returns:
            System prompt string
        """
        return f"""You are an AI assistant for the {self.use_case_name} use case.
You are helpful, knowledgeable, and provide clear and concise responses.
Always maintain context from the conversation history."""
    
    def format_chat_history(self, messages: List[ChatMessage]) -> List[Any]:
        """
        Format chat history into LangChain message format
        
        Args:
            messages: List of chat messages
            
        Returns:
            List of LangChain messages
        """
        formatted_messages = []
        
        # Add system message
        system_prompt = self.get_system_prompt()
        formatted_messages.append(SystemMessage(content=system_prompt))
        
        # Add conversation history
        for msg in messages:
            if msg.role == "user":
                formatted_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                formatted_messages.append(AIMessage(content=msg.content))
        
        return formatted_messages
    
    async def process_message(
        self, 
        user_message: str, 
        chat_history: List[ChatMessage],
        db: Optional[AsyncSession] = None,
        conversation_state: Optional[dict] = None
    ) -> AgentResponse:
        """
        Process a user message and generate a response.
        This is the main entry point for message processing.
        
        Args:
            user_message: The user's message
            chat_history: Previous conversation history
            db: Database session for context retrieval
            conversation_state: Current conversation state from previous messages
            
        Returns:
            AgentResponse with the generated message
        """
        # Load and initialize state
        self.current_state = self.load_state(conversation_state, chat_history)
        
        # Get relevant context (RAG)
        context = await self.get_relevant_context(user_message, db)
        
        # Format messages
        messages = self.format_chat_history(chat_history)
        messages.append(HumanMessage(content=user_message))
        
        # Allow subclasses to modify messages before generation
        messages = await self.preprocess_messages(messages, context)
        
        # Generate response
        response = await self.generate_response(messages)
        
        # Allow subclasses to postprocess the response
        response = await self.postprocess_response(response, context)
        
        return response
    
    async def get_relevant_context(
        self, 
        query: str,
        db: Optional[AsyncSession] = None,
        top_k: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve relevant context for the query (e.g., from vector database).
        Default implementation retrieves document chunks.
        Override this method for custom context retrieval.
        
        Args:
            query: The user's query
            db: Database session
            top_k: Number of relevant documents to retrieve
            
        Returns:
            Context dictionary or None
        """
        if not db:
            return None
            
        try:
            from embeddings import get_embedding
            from clients.database import DocumentChunkDB
            
            # Generate embedding for the query
            query_embedding = get_embedding(query)
            
            # Query for relevant chunks using cosine similarity
            result = await db.execute(
                select(DocumentChunkDB)
                .join(DocumentChunkDB.document)
                .filter(DocumentChunkDB.document.has(use_case_id=self.use_case_id))
                .order_by(DocumentChunkDB.embedding.cosine_distance(query_embedding))
                .limit(top_k)
            )
            chunks = result.scalars().all()
            
            if not chunks:
                return None
            
            # Format context
            context = {
                "relevant_chunks": [
                    {
                        "content": chunk.content,
                        "chunk_index": chunk.chunk_index,
                        "document_id": chunk.document_id
                    }
                    for chunk in chunks
                ],
                "num_chunks": len(chunks)
            }
            
            return context
            
        except Exception as e:
            print(f"Error retrieving context: {e}")
            return None
    
    async def preprocess_messages(
        self, 
        messages: List[Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Preprocess messages before generation.
        Default implementation adds document context if available.
        Override this to add custom preprocessing logic.
        
        Args:
            messages: List of formatted messages
            context: Additional context from get_relevant_context
            
        Returns:
            Modified list of messages
        """
        if context and context.get("relevant_chunks"):
            # Build context string
            context_str = "\n\nRelevant information from documents:\n"
            for i, chunk in enumerate(context["relevant_chunks"], 1):
                context_str += f"\n[Context {i}]:\n{chunk['content']}\n"
            
            # Add context to the last message (user's query)
            if messages and hasattr(messages[-1], 'content'):
                original_content = messages[-1].content
                messages[-1].content = f"{original_content}\n{context_str}"
        
        return messages
    
    async def generate_response(self, messages: List[Any]) -> AgentResponse:
        """
        Generate a response using the LLM.
        Override this to use LangGraph workflows or custom logic.
        
        Args:
            messages: List of formatted messages
            
        Returns:
            AgentResponse
        """
        response = await self.llm.ainvoke(messages)
        return AgentResponse(
            message=response.content,
            metadata={"model": self.llm.model_name}
        )
    
    async def postprocess_response(
        self, 
        response: AgentResponse, 
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Postprocess the response before returning.
        Override this to add citations, formatting, etc.
        
        Args:
            response: The generated response
            context: Optional context used for generation
            
        Returns:
            Processed AgentResponse
        """
        # Add conversation state to metadata
        if hasattr(self, 'current_state'):
            if response.metadata is None:
                response.metadata = {}
            response.metadata["conversation_state"] = self.current_state
        
        return response

