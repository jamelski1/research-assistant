import os
import json
import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class ResearchGapAgent:
    """Agent that finds and automatically adds papers to fill research gaps"""

    def __init__(self, claude_client=None, notion_client=None, discord_client=None):
        self.claude_client = claude_client
        self.notion_client = notion_client
        self.discord_client = discord_client
        self.arxiv_base = "http://export.arxiv.org/api/query"

    async def find_papers_for_gaps(self, research_gaps: str, key_concepts: List[str], original_title: str) -> Dict:
        """Find papers that address identified research gaps"""

        # Use Claude to generate better search queries if available
        search_queries = self._generate_search_queries(research_gaps, key_concepts)

        all_papers = []

        # Search with each query
        for query in search_queries[:2]:  # Use top 2 queries
            papers = await self.search_arxiv(query, max_results=3)
            all_papers.extend(papers)

        # Remove duplicates and rank by relevance
        unique_papers = self._deduplicate_papers(all_papers)

        # Use Claude to rank if available
        if self.claude_client and unique_papers:
            ranked_papers = self._rank_papers_by_relevance(unique_papers, research_gaps)
        else:
            ranked_papers = unique_papers

        summary = f"Found {len(ranked_papers)} papers addressing the research gaps"

        # Filter out duplicates from Notion
        new_paper = None
        for paper in ranked_papers:
            if not self.paper_exists_in_notion(paper['title']):
                new_paper = paper
                break

        return {
            'papers': [new_paper] if new_paper else [],
            'summary': summary,
            'search_queries': search_queries
        }

    def _generate_search_queries(self, research_gaps: str, key_concepts: List[str]) -> List[str]:
        """Generate targeted search queries"""
        queries = []

        # Basic query from gaps
        gap_query = ' '.join(research_gaps.split()[:10])
        queries.append(gap_query)

        # Query combining concepts
        if key_concepts:
            concept_query = f"{key_concepts[0]} {research_gaps.split()[0]}"
            queries.append(concept_query)

        # If Claude is available, get better queries
        if self.claude_client:
            try:
                prompt = f"""Generate 3 specific search queries to find papers addressing this research gap:
                Gap: {research_gaps}
                Concepts: {', '.join(key_concepts)}

                Return only the 3 queries, one per line."""

                response = self.claude_client.messages.create(
                    model="claude-3-opus-20240229",
                    max_tokens=150,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                )

                claude_queries = response.content[0].text.strip().split('\n')
                queries = [q.strip() for q in claude_queries if q.strip()][:3]

            except Exception as e:
                logger.error(f"Claude query generation failed: {e}")

        return queries

    async def search_arxiv(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search arXiv for papers"""
        try:
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'relevance'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.arxiv_base, params=params) as response:
                    if response.status == 200:
                        text = await response.text()

                        # Parse XML properly
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(text)

                        papers = []
                        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                            title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
                            summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
                            id_elem = entry.find('{http://www.w3.org/2005/Atom}id')
                            published_elem = entry.find('{http://www.w3.org/2005/Atom}published')

                            if title_elem is not None and id_elem is not None:
                                # Get authors
                                authors = []
                                for author in entry.findall('{http://www.w3.org/2005/Atom}author'):
                                    name_elem = author.find('{http://www.w3.org/2005/Atom}name')
                                    if name_elem is not None:
                                        authors.append(name_elem.text)

                                papers.append({
                                    'title': title_elem.text.strip().replace('\n', ' '),
                                    'abstract': summary_elem.text.strip() if summary_elem is not None else '',
                                    'url': id_elem.text,
                                    'pdf_url': id_elem.text.replace('abs', 'pdf') + '.pdf',
                                    'authors': authors,
                                    'date': published_elem.text[:10] if published_elem is not None else '',
                                    'source': 'arXiv'
                                })

                        return papers

        except Exception as e:
            logger.error(f"arXiv search error: {e}")

        return []

    def paper_exists_in_notion(self, title: str) -> bool:
        """Check if a paper with the given title already exists in Notion"""
        if not self.notion_client:
            return False

        try:
            response = self.notion_client.databases.query(
                database_id=os.getenv('NOTION_DATABASE_ID'),
                filter={
                    "property": "Title",
                    "rich_text": {
                        "contains": title[:30]  # Check partial match
                    }
                }
            )
            return len(response.get('results', [])) > 0
        except Exception as e:
            logger.error(f"Notion lookup failed: {e}")
            return False

    def _deduplicate_papers(self, papers: List[Dict]) -> List[Dict]:
        """Remove duplicate papers based on title similarity"""
        seen = set()
        unique = []

        for paper in papers:
            title_key = paper['title'].lower()[:50]
            if title_key not in seen:
                seen.add(title_key)
                unique.append(paper)

        return unique

    def _rank_papers_by_relevance(self, papers: List[Dict], research_gaps: str) -> List[Dict]:
        """Use Claude to rank papers by relevance to research gaps"""
        # For now, just return as-is
        # Could implement Claude ranking here
        return papers

    async def fetch_and_analyze_paper(self, paper_url: str) -> Dict:
        """Fetch paper content and analyze it"""
        try:
            # If it's an arXiv paper, try to get the PDF
            if 'arxiv.org' in paper_url:
                pdf_url = paper_url.replace('abs', 'pdf') + '.pdf'

                # For now, we'll use the abstract page
                async with aiohttp.ClientSession() as session:
                    async with session.get(paper_url) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')

                            # Extract metadata
                            title = soup.find('h1', class_='title')
                            title = title.text.replace('Title:', '').strip() if title else ''

                            abstract = soup.find('blockquote', class_='abstract')
                            abstract = abstract.text.replace('Abstract:', '').strip() if abstract else ''

                            # Get authors
                            authors = soup.find('div', class_='authors')
                            authors_list = []
                            if authors:
                                for a in authors.find_all('a'):
                                    authors_list.append(a.text.strip())

                            # Analyze with Claude if available
                            analysis = {
                                'title': title,
                                'abstract': abstract,
                                'authors': authors_list,
                                'url': paper_url,
                                'pdf_url': pdf_url,
                                'summary': abstract[:500] + '...' if len(abstract) > 500 else abstract,
                                'key_concepts': [],
                                'methodology': 'Not analyzed',
                                'theme': 'General'
                            }

                            if self.claude_client and abstract:
                                try:
                                    prompt = f"""Analyze this paper abstract and provide:
                                    1. 3-5 key concepts
                                    2. Research methodology (if mentioned)
                                    3. Which theme it fits: AI, LLM Hallucinations, Developer Workflows, QA, or General

                                    Title: {title}
                                    Abstract: {abstract[:1000]}

                                    Respond in JSON format with keys: key_concepts (array), methodology, theme"""

                                    response = self.claude_client.messages.create(
                                        model="claude-3-opus-20240229",
                                        max_tokens=300,
                                        temperature=0.5,
                                        messages=[{"role": "user", "content": prompt}]
                                    )

                                    # Parse response
                                    text = response.content[0].text
                                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                                    if json_match:
                                        claude_analysis = json.loads(json_match.group())
                                        analysis.update(claude_analysis)

                                except Exception as e:
                                    logger.error(f"Claude analysis failed: {e}")

                            return {
                                'success': True,
                                'data': analysis
                            }

            # For other sources, return basic info
            return {
                'success': True,
                'data': {
                    'title': 'External Paper',
                    'url': paper_url,
                    'summary': 'External paper - manual review needed'
                }
            }

        except Exception as e:
            logger.error(f"Failed to fetch paper: {e}")
            return {'success': False, 'error': str(e)}

    def add_paper_to_notion(self, paper_data: Dict, original_paper_title: str, theme: str,
                            source_paper_gaps: str) -> str:
        """Add the found paper to Notion database"""
        if not self.notion_client:
            return None

        try:
            data = paper_data['data']

            # Prepare notes with context
            notes = f"""Auto-added by Research Gap Agent
Source Paper: {original_paper_title}
Addressing Gaps: {source_paper_gaps[:200]}...
Added: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

            # Create Notion page
            response = self.notion_client.pages.create(
                parent={"database_id": os.getenv('NOTION_DATABASE_ID')},
                properties={
                    "Title": {"title": [{"text": {"content": data.get('title', 'Untitled Paper')[:100]}}]},
                    "Theme": {"select": {"name": data.get('theme', theme)}},
                    "Status": {"select": {"name": "To Read"}},  # New status for gap-filling papers
                    "Summary": {
                        "rich_text": [{"text": {"content": data.get('summary', data.get('abstract', ''))[:2000]}}]},
                    "Notes": {"rich_text": [{"text": {"content": notes}}]},
                    "Key Findings": {
                        "rich_text": [{"text": {"content": '\n'.join(data.get('key_concepts', []))[:2000]}}]},
                    "Research Gaps": {"rich_text": [{"text": {"content": "Gap-filling paper - review for insights"}}]},
                    "PDF Link": {"url": data.get('pdf_url', data.get('url', ''))}
                }
            )

            return response.get('url')

        except Exception as e:
            logger.error(f"Failed to add paper to Notion: {e}")
            return None

    def notify_paper_added(self, original_title: str, new_paper: Dict, notion_url: str):
        """Send Discord notification about newly added paper"""
        if not self.discord_client:
            return

        try:
            embed = {
                "title": "🎯 Gap-Filling Paper Added",
                "description": f"Found and added a paper to address research gaps",
                "color": 65280,  # Green
                "fields": [
                    {
                        "name": "📖 Original Paper",
                        "value": original_title[:100],
                        "inline": False
                    },
                    {
                        "name": "📄 New Paper Added",
                        "value": f"[{new_paper['title'][:80]}...]({new_paper['url']})",
                        "inline": False
                    },
                    {
                        "name": "📝 Status",
                        "value": "Added to Notion as 'To Read'",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "Research Gap Agent"
                },
                "timestamp": datetime.now().isoformat()
            }

            if notion_url:
                embed["fields"].append({
                    "name": "🔗 Notion Link",
                    "value": f"[View in Notion]({notion_url})",
                    "inline": True
                })

            response = requests.post(
                self.discord_client.webhook_url,
                json={"embeds": [embed]}
            )

        except Exception as e:
            logger.error(f"Discord notification failed: {e}")