import requests
import json
from datetime import datetime
import logging

class DiscordNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)

    def send_research_update(self, summary_data):
        """Send formatted research update to Discord"""
        embed = {
            "title": "📚 PhD Research Update",
            "description": f"Progress summary for {datetime.now().strftime('%B %d, %Y')}",
            "color": 5814783,  # Academic blue
            "fields": [],
            "footer": {
                "text": "Research Assistant | JamelLawson.com"
            }
        }

        # Add progress fields
        if summary_data.get("papers_updated"):
            embed["fields"].append({
                "name": "📝 Papers Updated",
                "value": "\n".join([f"• {p}" for p in summary_data["papers_updated"]]),
                "inline": False
            })

        if summary_data.get("new_literature"):
            embed["fields"].append({
                "name": "🔍 New Literature Found",
                "value": f"{len(summary_data['new_literature'])} relevant papers discovered",
                "inline": True
            })

        if summary_data.get("writing_suggestions"):
            embed["fields"].append({
                "name": "💡 Writing Suggestions",
                "value": summary_data["writing_suggestions"][:1024],  # Discord limit
                "inline": False
            })

        if summary_data.get("next_milestones"):
            embed["fields"].append({
                "name": "🎯 Next Milestones",
                "value": "\n".join([f"• {m}" for m in summary_data["next_milestones"]]),
                "inline": False
            })

        payload = {
            "username": "Research Assistant",
            "embeds": [embed]
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            self.logger.info("Discord notification sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to send Discord notification: {e}")

    def send_message(self, message):
        """Send a plain text message to the Discord webhook"""
        payload = {
            "username": "Research Assistant",
            "content": message
        }
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            self.logger.info("Plain message sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to send plain Discord message: {e}")
