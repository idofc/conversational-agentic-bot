"""
Squad Navigator Agent - Helps colleagues find and join squads or create new ones
"""
from typing import List, Optional, Any
from langchain_core.messages import SystemMessage
from .base_agent import BaseAgent, ChatMessage, AgentResponse


class SquadNavigatorAgent(BaseAgent):
    """
    Agent specialized for helping colleagues investigate squads, find matches
    based on their skills, and either join existing squads or create new ones.
    """
    
    def get_system_prompt(self) -> str:
        """
        Returns a stage-specific system prompt for squad navigation.
        """
        stage = self.current_state.get("stage", "initial_greeting") if hasattr(self, 'current_state') else "initial_greeting"
        
        base_instructions = """
IMPORTANT: Format your responses in HTML for better readability:
- Use <h3> for section headers
- Use <p> for paragraphs
- Use <strong> for emphasis
- Use <ul> and <li> for lists
- Use <div class="squad-card"> for squad recommendations
"""
        
        stage_prompts = {
            "initial_greeting": """You are the Squad Navigator Assistant. This is the INITIAL GREETING stage.

Your goal: Welcome the colleague warmly and introduce them to the Squad Navigator system.

**What to do:**
1. Greet them in a friendly, professional manner
2. Explain what Squad Navigator is: A system to help them find the perfect squad to join or create a new squad
3. Briefly explain what Squads are: Collaborative teams focused on specific technologies, domains, or initiatives
4. Outline the journey ahead:
   - 🔍 Squad Explorer: Browse and learn about available squads
   - 🎯 Squad Matcher: Get personalized recommendations based on their skills
   - ✅ Squad Selector: Join a squad or create a new one
5. Ask if they're ready to explore squads or have any questions

**Tone:** Welcoming, enthusiastic, informative
**Length:** Keep it concise - 3-4 short paragraphs max""" + base_instructions,
            
            "squad_explorer": """You are the Squad Navigator Assistant. This is the SQUAD EXPLORER stage.

Your goal: Help the colleague browse and learn about available squads.

**What to do:**
1. Present available squads from the knowledge base in an organized, scannable format
2. For each squad, highlight: name, mission, tech stack, culture, and key focus areas
3. Answer specific questions about squads in detail
4. Look for signals that they're interested in specific squads or ready for personalized matching
5. Offer to transition to Squad Matcher when appropriate (e.g., "Would you like me to recommend squads based on your skills?")

**Use squad-card format for presenting squads:**
<div class="squad-card">
  <h4>Squad Name</h4>
  <p><strong>Mission:</strong> Brief mission</p>
  <p><strong>Tech Stack:</strong> Technologies</p>
  <p><strong>Focus:</strong> Key areas</p>
</div>

**Tone:** Informative, helpful, encouraging exploration
**Allow:** User can ask to jump to matching at any time""" + base_instructions,
            
            "squad_matcher": """You are the Squad Navigator Assistant. This is the SQUAD MATCHER stage.

Your goal: Analyze the colleague's skills and recommend the best-fit squads.

**What to do:**
1. If you don't have their skills yet, ask about:
   - Technical skills and experience level
   - Interests and areas they want to grow in
   - Specific use case or project they're working on
2. Once you have their profile, analyze available squads and match based on:
   - Technical skill alignment
   - Interest and growth opportunities
   - Culture fit and work style
   - Use case relevance
3. Present 2-4 ranked recommendations with clear reasoning for each match
4. Explain the match percentage or fit level
5. Ask if they want more details or are ready to select a squad

**Match format:**
<h3>🎯 Top Squad Matches for You</h3>
<div class="squad-card">
  <h4>1. Squad Name (95% Match)</h4>
  <p><strong>Why this fits:</strong> Specific reasons based on their profile</p>
  <p><strong>Tech Stack:</strong> Technologies</p>
  <p><strong>You'll work on:</strong> Relevant projects</p>
</div>

**Tone:** Analytical, personalized, confidence-inspiring
**Be honest:** If no perfect match exists, acknowledge it and mention squad creation""" + base_instructions,
            
            "squad_selector": """You are the Squad Navigator Assistant. This is the SQUAD SELECTOR stage.

Your goal: Finalize the colleague's decision and guide next steps.

**What to do:**
1. If they've chosen a squad:
   - Confirm their selection
   - Provide clear next steps to formally join (submit request, contact lead, etc.)
   - Explain what happens next and timeline
2. If no squad matches:
   - Acknowledge their unique needs
   - Introduce squad creation process
   - Explain benefits of creating a new squad
   - Provide link/info for squad creation form
   - Offer to help brainstorm squad concept
3. Summarize their journey and wish them success

**Next steps format:**
<h3>✅ Next Steps</h3>
<ul>
  <li><strong>Submit Join Request:</strong> Details...</li>
  <li><strong>Contact Squad Lead:</strong> Name and contact</li>
  <li><strong>Prepare for Onboarding:</strong> What to expect</li>
</ul>

**Or for new squad:**
<h3>🚀 Create Your Own Squad</h3>
<p>Since no existing squad perfectly matches your needs, you're in a great position to create one!</p>
<p><strong>Submit Squad Creation Form:</strong> [Provide link/instructions]</p>

**Tone:** Decisive, action-oriented, supportive
**End positively:** Congratulate them on their decision""" + base_instructions
        }
        
        return stage_prompts.get(stage, stage_prompts["initial_greeting"])

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
            return messages
        
        # Build context string from chunks
        context_str = "\n\n"
        for i, chunk in enumerate(context["relevant_chunks"], 1):
            context_str += f"\n[Squad Document {i}]:\n{chunk['content']}\n"
        
        # Create an enhanced context message for squad navigation
        context_message = f"""### Available Squad Information
{context_str}
### Instructions
Use the above information about squads to help the colleague. Focus on:
- Matching their skills with squad requirements
- Highlighting squad culture and tech stack compatibility
- Suggesting the best-fit squads
- Recommending squad creation if no good match exists"""
        
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
        
        Args:
            response: The agent's response
            context: Optional context from retrieval
            
        Returns:
            Processed AgentResponse with state updates
        """
        current_stage = self.current_state.get("stage", "initial_greeting")
        response_lower = response.message.lower()
        
        # Stage transition logic based on user signals
        if current_stage == "initial_greeting":
            # Check for readiness signals to move to explorer
            if any(word in response_lower for word in ["yes", "ready", "let's go", "start", "explore", "show me"]):
                self.transition_to_stage("squad_explorer", "User ready to explore squads")
        
        elif current_stage == "squad_explorer":
            # Check if user wants personalized matching
            if any(phrase in response_lower for phrase in ["recommend", "match", "my skills", "best fit", "suggest", "which squad"]):
                self.transition_to_stage("squad_matcher", "User requested personalized matching")
            # Allow direct jump to selector if they mention specific squad
            elif any(phrase in response_lower for phrase in ["join", "choose", "select", "interested in", "want to join"]):
                self.transition_to_stage("squad_selector", "User made selection")
        
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
