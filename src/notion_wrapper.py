import os
from notion_client import Client
from datetime import datetime
import logging

class NotionResearchTracker:
    def __init__(self, api_key, database_id):
        self.notion = Client(auth=api_key)
        self.database_id = database_id
        self.logger = logging.getLogger(__name__)
        
    def create_paper_entry(self, title, theme, status="Draft", summary="", notes=""):
        """Create a new paper entry in Notion"""
        try:
            response = self.notion.pages.create(
                parent={"database_id": self.database_id},
                properties={
                    "Title": {"title": [{"text": {"content": title}}]},
                    "Theme": {"select": {"name": theme}},
                    "Status": {"select": {"name": status}},
                    "Summary": {"rich_text": [{"text": {"content": summary}}]},
                    "Notes": {"rich_text": [{"text": {"content": notes}}]},
                    "Last Updated": {"date": {"start": datetime.now().isoformat()}}
                }
            )
            self.logger.info(f"Created Notion entry for: {title}")
            return response
        except Exception as e:
            self.logger.error(f"Failed to create Notion entry: {e}")
            raise
            
    def update_paper_progress(self, page_id, updates):
        """Update existing paper entry"""
        try:
            response = self.notion.pages.update(
                page_id=page_id,
                properties=updates
            )
            return response
        except Exception as e:
            self.logger.error(f"Failed to update Notion entry: {e}")
            raise
            
    def get_recent_changes(self, hours=48):
        """Get papers modified in the last N hours"""
        from datetime import datetime, timedelta
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        try:
            response = self.notion.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "Last Updated",
                    "date": {"after": since}
                }
            )
            return response["results"]
        except Exception as e:
            self.logger.error(f"Failed to query Notion: {e}")
            return []