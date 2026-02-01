# Agents Package

This package contains agent implementations for the conversational agentic bot. Each agent inherits from the `BaseAgent` class and can customize behavior for specific use cases.

## Architecture

### BaseAgent (base_agent.py)
The generic base class that provides:
- **RAG (Retrieval Augmented Generation)**: Retrieves relevant document chunks using vector similarity
- **LangChain Integration**: Uses `ChatOpenAI` for LLM interactions
- **Extensibility Hooks**: Methods that can be overridden by subclasses:
  - `get_system_prompt()`: Returns system instructions for the agent
  - `preprocess_messages()`: Modifies messages before sending to LLM
  - `postprocess_response()`: Processes LLM response before returning

### SquadNavigatorAgent (squad_navigator_agent.py)
Specialized agent for helping colleagues find and join squads or create new ones.

**Features:**
- Custom system prompt focused on squad investigation and skills matching
- Enhanced context handling for squad information
- Intelligent postprocessing that detects:
  - Squad creation suggestions (adds creation steps)
  - Squad joining recommendations (adds joining steps)
- Metadata enrichment with actionable next steps

**Use Case:** `squad-navigator`

## Usage

Agents are automatically selected in `main.py` based on the use case URI context:

```python
if use_case.uri_context == "squad-navigator":
    agent = SquadNavigatorAgent(use_case_id=use_case.id, use_case_name=use_case.name)
else:
    agent = BaseAgent(use_case_id=use_case.id, use_case_name=use_case.name)
```

## Creating New Agents

To create a new specialized agent:

1. Create a new file in `backend/agents/` (e.g., `my_agent.py`)
2. Import and extend `BaseAgent`:
   ```python
   from .base_agent import BaseAgent, ChatMessage, AgentResponse
   
   class MyAgent(BaseAgent):
       def get_system_prompt(self) -> str:
           return "Your specialized system prompt"
       
       def preprocess_messages(self, messages, context):
           # Custom message preprocessing
           return messages
       
       def postprocess_response(self, response, context):
           # Custom response postprocessing
           return response
   ```
3. Export the agent in `__init__.py`
4. Add agent selection logic in `main.py`

## Example Conversation

**User:** "Hi! I am a backend developer with Python, FastAPI, PostgreSQL, and Docker skills. Looking for a squad to join."

**SquadNavigatorAgent Response:**
- Analyzes skills
- Suggests relevant squads (Backend Microservices Squad, Platform Engineering Squad, API Development Squad)
- Provides details about each squad (mission, tech stack, culture)
- Asks clarifying questions about preferences
- Adds metadata with next steps for joining or creating squads

## Testing

Test agents via the API:
```bash
curl -X POST http://localhost:8000/api/use-cases/squad-navigator/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I have Python and FastAPI skills. Help me find a squad."}'
```
