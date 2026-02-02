"""
Squad Navigator Agent - Helps colleagues find and join squads or create new ones
"""
from typing import List, Optional, Any
from langchain_core.messages import SystemMessage
from .base_agent import BaseAgent, ChatMessage, AgentResponse
from prompts import SQUAD_NAVIGATOR_PROMPTS


class SquadNavigatorAgent(BaseAgent):
    """
    Agent specialized for helping colleagues investigate squads, find matches
    based on their skills, and either join existing squads or create new ones.
    """
    
    def get_system_prompt(self) -> str:
        """
        Returns a stage-specific system prompt for squad navigation.
        Prompts are now loaded from the prompts module.
        """
        stage = self.current_state.get("stage", "initial_greeting") if hasattr(self, 'current_state') else "initial_greeting"
        return SQUAD_NAVIGATOR_PROMPTS.get(stage, SQUAD_NAVIGATOR_PROMPTS["initial_greeting"])

    async def preprocess_messages(
        self, 
        messages: List[Any], 
        context: Optional[Any] = None
    ) -> List[Any]:
        """
        Preprocesses messages with squad-specific context handling.
        Adds relevant squad information as context.
        
        Args:
            messages: List of LangChain message objects (HumanMessage, AIMessage, SystemMessage)
            context: Optional context dict from RAG with relevant_chunks
            
        Returns:
            List of LangChain message objects with injected context
        """
        if not context or not context.get("relevant_chunks"):
            # No context available - add message to inform agent
            no_context_message = SystemMessage(content="""### ⚠️ CRITICAL NOTICE
No squad documents were found in the knowledge base for this use case.
You MUST inform the user that:
1. No squad information is currently available
2. They need to upload squad documents first
3. DO NOT make up or invent example squads
4. DO NOT use generic squad names like "Innovators", "Data Wizards", etc.

Respond politely explaining that squad documents need to be uploaded to this use case before you can help them explore squads.""")
            
            # Add no-context message before last user message
            enhanced_messages = messages[:-1].copy() if len(messages) > 1 else []
            enhanced_messages.append(no_context_message)
            if messages:
                enhanced_messages.append(messages[-1])
            return enhanced_messages
        
        # Build context string from chunks
        context_str = "\n\n"
        for i, chunk in enumerate(context["relevant_chunks"], 1):
            context_str += f"\n[Squad Document {i}]:\n{chunk['content']}\n"
        
        # Create an enhanced context message for squad navigation
        context_message = f"""### 🎯 Available Squad Information (USE ONLY THIS DATA)
{context_str}

### ⚠️ CRITICAL INSTRUCTIONS
⚠️ You MUST use ONLY the squad information provided above.
⚠️ DO NOT invent, create, or hallucinate squad names, missions, or details.
⚠️ DO NOT use example squads like "Innovators", "Data Wizards", "Cloud Pioneers", or "Creative Coders".
⚠️ If the user asks about squads, present ONLY the squads from the documents above.
⚠️ Match their skills ONLY against the squads provided above.
⚠️ If no good match exists in the provided squads, recommend creating a new squad."""
        
        # Inject context before the last user message
        enhanced_messages = messages[:-1].copy() if len(messages) > 1 else []
        
        # Add context as a LangChain SystemMessage
        enhanced_messages.append(SystemMessage(content=context_message))
        
        # Add the user's current message
        if messages:
            enhanced_messages.append(messages[-1])
        
        return enhanced_messages
    
    async def postprocess_response(self, response: AgentResponse, context: Optional[Any] = None) -> AgentResponse:
        """
        Post-processes the response to handle stage transitions and extract user information.
        Enforces SEQUENTIAL navigation - users cannot skip stages.
        
        Args:
            response: The agent's response
            context: Optional context from retrieval
            
        Returns:
            Processed AgentResponse with state updates
        """
        current_stage = self.current_state.get("stage", "initial_greeting")
        response_lower = response.message.lower()
        
        # Track completed stages for sequential enforcement
        completed_stages = self.current_state.get("completed_stages", [])
        if current_stage not in completed_stages:
            completed_stages.append(current_stage)
            self.update_state({"completed_stages": completed_stages})
        
        # Stage transition logic - SEQUENTIAL ONLY (no skipping allowed)
        if current_stage == "initial_greeting":
            # Can only move to squad_explorer (next stage)
            if any(word in response_lower for word in ["yes", "ready", "let's go", "start", "explore", "show me"]):
                self.transition_to_stage("squad_explorer", "User ready to explore squads")
        
        elif current_stage == "squad_explorer":
            # Detect if user is trying to skip to selector
            if any(phrase in response_lower for phrase in ["join", "choose", "select", "interested in", "want to join"]):
                # Block skip attempt - set flag for agent to redirect
                self.update_state({
                    "skip_attempt": True,
                    "skip_attempt_target": "squad_selector",
                    "skip_attempt_count": self.current_state.get("skip_attempt_count", 0) + 1
                })
                # Stay in current stage - do not transition
            # Allow progression to squad_matcher (next sequential stage)
            elif any(phrase in response_lower for phrase in ["recommend", "match", "my skills", "best fit", "suggest", "which squad", "next", "continue"]):
                self.transition_to_stage("squad_matcher", "User requested personalized matching")
        
        elif current_stage == "squad_matcher":
            # Extract skills from user input if present (simple keyword detection)
            skills_keywords = ["python", "javascript", "java", "react", "node", "fastapi", "django", "flask", 
                             "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
                             "postgres", "mongodb", "redis", "sql", "nosql", "api", "rest", "graphql",
                             "machine learning", "ml", "ai", "data", "backend", "frontend", "fullstack"]
            detected_skills = [skill for skill in skills_keywords if skill in response_lower]
            
            if detected_skills:
                existing_skills = self.current_state.get("user_profile", {}).get("skills", [])
                all_skills = list(set(existing_skills + detected_skills))
                self.update_state({
                    "user_profile": {
                        "skills": all_skills,
                        "raw_input": response_lower[:300]
                    }
                })
            
            # Check if user is ready to select a squad
            if any(phrase in response_lower for phrase in ["join", "choose", "select", "go with", "pick", "i'll take"]):
                self.transition_to_stage("squad_selector", "User ready to select squad")
        
        elif current_stage == "squad_selector":
            # Check if user confirmed or wants to create new squad
            if any(phrase in response_lower for phrase in ["new squad", "create squad", "form", "start my own"]):
                self.update_state({
                    "context_data": {
                        "decision": "create_new_squad"
                    }
                })
        
        # Ensure HTML formatting
        response.message = self._ensure_html_format(response.message)
        
        # Add stage info to metadata
        if response.metadata is None:
            response.metadata = {}
        
        response.metadata["current_stage"] = self.current_state.get("stage")
        response.metadata["conversation_state"] = self.current_state
        response.metadata["completed_stages"] = self.current_state.get("completed_stages", [])
        
        # Add skip attempt warning to metadata if detected
        if self.current_state.get("skip_attempt"):
            response.metadata["skip_attempt_detected"] = True
            response.metadata["skip_message"] = "User attempted to skip stages - agent should redirect"
            # Clear the flag after detection
            self.update_state({"skip_attempt": False})
        
        # Legacy metadata for compatibility
        if "create" in response_lower or "new squad" in response_lower:
            response.metadata["suggestion_type"] = "create_squad"
            response.metadata["next_steps"] = [
                "Fill out the squad creation form",
                "Define your squad's mission and goals",
                "Recruit initial team members"
            ]
        elif any(word in response_lower for word in ["join", "match", "recommend"]):
            response.metadata["suggestion_type"] = "join_existing"
            response.metadata["next_steps"] = [
                "Review the recommended squads",
                "Reach out to squad leads",
                "Submit a join request"
            ]
        
        return response
    
    def _ensure_html_format(self, text: str) -> str:
        """
        Ensures the text is properly formatted as HTML.
        If the text doesn't contain HTML tags, wraps it in basic HTML.
        """
        # Remove markdown code fence markers if present
        text = text.strip()
        if text.startswith('```html'):
            text = text[7:].strip()
        elif text.startswith('```'):
            text = text[3:].strip()
        if text.endswith('```'):
            text = text[:-3].strip()
        
        # Check if text already contains HTML tags
        if '<' in text and '>' in text:
            # Clean up excessive whitespace and blank lines in HTML
            import re
            # Remove multiple consecutive newlines
            text = re.sub(r'\n\s*\n+', '\n', text)
            # Remove newlines between closing and opening tags
            text = re.sub(r'>\s+<', '><', text)
            return text.strip()
        
        # Convert plain text to HTML with basic formatting
        lines = text.split('\n')
        html_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                continue
            
            # Check for list items (lines starting with -, *, or numbers)
            if line.startswith(('- ', '* ', '• ')) or (len(line) > 2 and line[0].isdigit() and line[1] in ('.', ')')):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                # Remove list marker
                item_text = line.lstrip('-*•0123456789.) ')
                html_lines.append(f'<li>{item_text}</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                
                # Check for headers (lines ending with :)
                if line.endswith(':') and len(line) < 100:
                    html_lines.append(f'<h4>{line[:-1]}</h4>')
                else:
                    # Regular paragraph
                    # Replace **text** with <strong>text</strong>
                    line = line.replace('**', '<strong>', 1)
                    if '<strong>' in line:
                        line = line.replace('**', '</strong>', 1)
                    html_lines.append(f'<p>{line}</p>')
        
        if in_list:
            html_lines.append('</ul>')
        
        # Join without newlines to avoid blank lines in rendered HTML
        return ''.join(html_lines)
