from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging

class ResearchScheduler:
    def __init__(self, notion, discord, claude, config):
        self.notion = notion
        self.discord = discord
        self.claude = claude
        self.config = config
        self.scheduler = BackgroundScheduler()
        self.logger = logging.getLogger(__name__)
        
    def start(self):
        """Start scheduled tasks"""
        frequency = self.config['notifications']['discord']['frequency_hours']
        
        # Schedule Discord updates
        self.scheduler.add_job(
            func=self.send_research_update,
            trigger='interval',
            hours=frequency,
            id='discord_update',
            name='Send Discord Research Update'
        )
        
        self.scheduler.start()
        self.logger.info(f"Scheduler started with {frequency}h update frequency")
        
    def update_frequency(self, new_hours):
        """Update notification frequency"""
        self.scheduler.remove_job('discord_update')
        self.scheduler.add_job(
            func=self.send_research_update,
            trigger='interval',
            hours=new_hours,
            id='discord_update',
            name='Send Discord Research Update'
        )
        self.logger.info(f"Update frequency changed to {new_hours} hours")
        
    async def send_research_update(self):
        """Generate and send research update"""
        try:
            # Get recent changes from Notion
            recent_papers = self.notion.get_recent_changes(
                hours=self.config['notifications']['discord']['frequency_hours']
            )
            
            # Generate summary
            summary_data = {
                'papers_updated': [p['properties']['Title']['title'][0]['text']['content'] 
                                 for p in recent_papers],
                'writing_suggestions': '',
                'next_milestones': []
            }
            
            # Get AI-powered suggestions if papers were updated
            if recent_papers:
                latest_paper = recent_papers[0]
                suggestions = self.claude.generate_writing_suggestions(
                    paper_status=latest_paper['properties']['Status']['select']['name'],
                    recent_notes=latest_paper['properties']['Notes']['rich_text'][0]['text']['content']
                )
                summary_data['writing_suggestions'] = suggestions
                
            # Send to Discord
            self.discord.send_research_update(summary_data)
            
        except Exception as e:
            self.logger.error(f"Failed to send research update: {e}")