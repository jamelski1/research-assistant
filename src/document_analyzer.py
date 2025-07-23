import os
import PyPDF2
from typing import Dict, List, Optional
import logging

class DocumentAnalyzer:
    """Handle PDF processing and text extraction"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def extract_text(self, filepath: str) -> str:
        """Extract text from PDF file"""
        try:
            text = ""
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                self.logger.info(f"Processing PDF with {num_pages} pages")
                
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
                    
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"Error extracting text from PDF: {e}")
            return ""
            
    def extract_metadata(self, filepath: str) -> Dict:
        """Extract metadata from PDF"""
        try:
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                metadata = pdf_reader.metadata
                
                if metadata:
                    return {
                        'title': metadata.get('/Title', 'Unknown'),
                        'author': metadata.get('/Author', 'Unknown'),
                        'subject': metadata.get('/Subject', ''),
                        'creator': metadata.get('/Creator', ''),
                        'pages': len(pdf_reader.pages)
                    }
                    
            return {'pages': len(pdf_reader.pages)}
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {e}")
            return {}
            
    def chunk_text(self, text: str, chunk_size: int = 3000) -> List[str]:
        """Split text into chunks for processing"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0
        
        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1
            
            if current_size >= chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0
                
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
        return chunks
        
    def extract_sections(self, text: str) -> Dict[str, str]:
        """Try to extract common paper sections"""
        sections = {
            'abstract': '',
            'introduction': '',
            'methodology': '',
            'results': '',
            'conclusion': '',
            'references': ''
        }
        
        # Simple section extraction (can be improved)
        text_lower = text.lower()
        
        # Look for section headers
        section_keywords = {
            'abstract': ['abstract'],
            'introduction': ['introduction', '1. introduction', '1 introduction'],
            'methodology': ['methodology', 'methods', 'method'],
            'results': ['results', 'findings'],
            'conclusion': ['conclusion', 'conclusions', 'discussion'],
            'references': ['references', 'bibliography', 'works cited']
        }
        
        for section, keywords in section_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Find the section
                    start_idx = text_lower.index(keyword)
                    # Extract a portion (this is simplified)
                    sections[section] = text[start_idx:start_idx+1000][:500] + "..."
                    break
                    
        return sections