from anthropic import Anthropic
import json
import logging

class ClaudeResearchAnalyzer:
    def __init__(self, api_key):
        self.client = Anthropic(api_key=api_key)
        self.logger = logging.getLogger(__name__)
        
    def analyze_paper(self, pdf_text, research_context=None):
        """Analyze uploaded paper for key insights and gaps"""
        prompt = f"""You are an expert research assistant helping with a PhD in Information Systems 
        focusing on AI, LLM hallucinations, developer workflows, and quality assurance.
        
        Analyze this paper and provide:
        1. Key concepts and contributions
        2. Methodological approach
        3. Research gaps or limitations
        4. Connection to ongoing research themes
        5. Suggestions for building upon this work
        
        Paper text:
        {pdf_text[:8000]}  # Truncate for token limits
        
        {"Current research context: " + research_context if research_context else ""}
        
        Provide structured analysis in JSON format.
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=4000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            analysis = json.loads(response.content[0].text)
            return analysis
        except Exception as e:
            self.logger.error(f"Claude analysis failed: {e}")
            return None
            
    def generate_writing_suggestions(self, paper_status, recent_notes):
        """Generate actionable writing suggestions"""
        prompt = f"""Based on the current research status, provide specific, actionable 
        writing suggestions for advancing this PhD paper.
        
        Current status: {paper_status}
        Recent notes: {recent_notes}
        
        Focus on:
        1. Next logical sections to write
        2. Key arguments to develop
        3. Evidence or examples needed
        4. Methodological considerations
        5. Quality assurance checkpoints
        
        Be specific and practical.
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=2000,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Failed to generate suggestions: {e}")
            return "Unable to generate suggestions at this time."