import aiohttp
import asyncio
from typing import List, Dict
import logging
from datetime import datetime

class AcademicSearchAggregator:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.enabled_sources = []
        self._initialize_sources()
        
    def _initialize_sources(self):
        """Initialize enabled academic sources"""
        if self.config['databases']['semantic_scholar']['enabled']:
            self.enabled_sources.append('semantic_scholar')
        if self.config['databases']['arxiv']['enabled']:
            self.enabled_sources.append('arxiv')
        if self.config['databases']['ieee']['enabled']:
            self.enabled_sources.append('ieee')
        # Add more as configured
            
    async def search_all_sources(self, query: str, max_results: int = 10) -> Dict[str, List]:
        """Search across all enabled academic databases"""
        results = {}
        tasks = []
        
        async with aiohttp.ClientSession() as session:
            if 'semantic_scholar' in self.enabled_sources:
                tasks.append(self._search_semantic_scholar(session, query, max_results))
            if 'arxiv' in self.enabled_sources:
                tasks.append(self._search_arxiv(session, query, max_results))
            if 'ieee' in self.enabled_sources:
                tasks.append(self._search_ieee(session, query, max_results))
                
            search_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for source, result in zip(self.enabled_sources, search_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Search failed for {source}: {result}")
                    results[source] = {"status": "error", "papers": []}
                else:
                    results[source] = {"status": "success", "papers": result}
                    
        return results
        
    async def _search_semantic_scholar(self, session, query, limit):
        """Search Semantic Scholar API"""
        url = f"{self.config['databases']['semantic_scholar']['base_url']}/paper/search"
        params = {
            'query': query,
            'limit': limit,
            'fields': 'title,authors,year,abstract,citationCount,url'
        }
        
        headers = {}
        if api_key := self.config['databases']['semantic_scholar'].get('api_key'):
            headers['x-api-key'] = api_key
            
        async with session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return self._format_papers(data.get('data', []), 'semantic_scholar')
            else:
                raise Exception(f"Semantic Scholar API error: {response.status}")
                
    async def _search_arxiv(self, session, query, limit):
        """Search arXiv API"""
        url = self.config['databases']['arxiv']['base_url'] + '/query'
        params = {
            'search_query': f'all:{query}',
            'start': 0,
            'max_results': limit,
            'sortBy': 'relevance'
        }
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                # Parse arXiv XML response (simplified)
                text = await response.text()
                # XML parsing logic here
                papers = []  # Parsed papers
                return self._format_papers(papers, 'arxiv')
            else:
                raise Exception(f"arXiv API error: {response.status}")
                
    def _format_papers(self, papers, source):
        """Standardize paper format across sources"""
        formatted = []
        for paper in papers:
            formatted.append({
                'title': paper.get('title', ''),
                'authors': paper.get('authors', []),
                'year': paper.get('year', ''),
                'abstract': paper.get('abstract', ''),
                'url': paper.get('url', ''),
                'source': source,
                'relevance_score': paper.get('citationCount', 0)  # Or other metric
            })
        return formatted