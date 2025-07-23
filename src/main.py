import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

# Set up logger
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Create app
app = Flask(__name__,
            template_folder='../web/templates',
            static_folder='../web/static')
app.config['UPLOAD_FOLDER'] = 'data/cache'

# Track which services initialize successfully
services = {
    'notion': False,
    'discord': False,
    'claude': False
}

# Initialize Notion
if os.getenv('NOTION_API_KEY') and 'YOUR_' not in os.getenv('NOTION_API_KEY', ''):
    try:
        from notion_client import Client
        notion_client = Client(auth=os.getenv('NOTION_API_KEY'))
        services['notion'] = True
        logger.info("✅ Notion client initialized")
    except Exception as e:
        logger.error(f"Notion setup failed: {e}")

# Initialize Discord
if os.getenv('DISCORD_WEBHOOK_URL') and 'YOUR_' not in os.getenv('DISCORD_WEBHOOK_URL', ''):
    try:
        from discord_notifier import DiscordNotifier
        discord_client = DiscordNotifier(os.getenv('DISCORD_WEBHOOK_URL'))
        discord_client.send_message("🚀 Research Assistant Started!")
        services['discord'] = True
        logger.info("✅ Discord client initialized")
    except Exception as e:
        logger.error(f"Discord setup failed: {e}")

# Initialize Claude
if os.getenv('ANTHROPIC_API_KEY') and 'YOUR_' not in os.getenv('ANTHROPIC_API_KEY', ''):
    try:
        from anthropic import Anthropic
        claude_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        services['claude'] = True
        logger.info("✅ Claude client initialized")
    except Exception as e:
        logger.error(f"Claude setup failed: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/upload')
def upload():
    return render_template('upload.html')

# Complete upload route
@app.route('/upload', methods=['GET', 'POST'])
def upload_paper():
    """Handle PDF uploads with full processing"""
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                # Save the file
                file.save(filepath)
                logger.info(f"File uploaded: {filename}")
                
                # Extract text from PDF
                extracted_text = ""
                try:
                    import PyPDF2
                    with open(filepath, 'rb') as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        num_pages = len(pdf_reader.pages)
                        
                        # Extract text from first 10 pages (or all if less)
                        pages_to_read = min(num_pages, 10)
                        for page_num in range(pages_to_read):
                            page = pdf_reader.pages[page_num]
                            extracted_text += page.extract_text() + "\n"
                        
                        logger.info(f"Extracted {len(extracted_text)} characters from {pages_to_read} pages")
                except Exception as e:
                    logger.error(f"PDF extraction error: {e}")
                    extracted_text = ""
                
                # Initialize analysis result
                analysis = {
                    'title': filename.replace('.pdf', ''),
                    'summary': 'Processing...',
                    'key_concepts': [],
                    'research_gaps': '',
                    'methodology': '',
                    'primary_theme': request.form.get('theme', 'General'),
                    'filename': filename,
                    'pages': 0,
                    'extraction_success': bool(extracted_text)
                }
                
                # Get Claude analysis if available and text was extracted
                if claude_client and extracted_text:
                    try:
                        # Prepare the prompt
                        prompt = f"""You are an expert research assistant helping with a PhD in Information Systems 
                        focusing on AI, LLM hallucinations, developer workflows, and quality assurance.
                        
                        Analyze this academic paper and provide:
                        1. A concise title (if you can identify it)
                        2. A 2-3 sentence summary
                        3. 3-5 key concepts or contributions
                        4. Research gaps or limitations identified
                        5. The primary research methodology used
                        6. Which theme it best fits: AI, LLM Hallucinations, Developer Workflows, QA, or General
                        
                        Paper text (first 10 pages):
                        {extracted_text[:8000]}  # Limit to ~8000 chars for token limits
                        
                        Respond in JSON format with keys: title, summary, key_concepts (array), 
                        research_gaps, methodology, suggested_theme"""
                        
                        # Call Claude
                        response = claude_client.messages.create(
                            model="claude-3-opus-20240229",
                            max_tokens=1000,
                            temperature=0.7,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        
                        # Parse Claude's response
                        claude_text = response.content[0].text
                        
                        # Try to parse as JSON
                        try:
                            # Look for JSON in the response
                            import re
                            json_match = re.search(r'\{.*\}', claude_text, re.DOTALL)
                            if json_match:
                                claude_analysis = json.loads(json_match.group())
                                
                                # Update analysis with Claude's insights
                                analysis.update({
                                    'title': claude_analysis.get('title', analysis['title']),
                                    'summary': claude_analysis.get('summary', 'No summary available'),
                                    'key_concepts': claude_analysis.get('key_concepts', []),
                                    'research_gaps': claude_analysis.get('research_gaps', ''),
                                    'methodology': claude_analysis.get('methodology', ''),
                                    'suggested_theme': claude_analysis.get('suggested_theme', analysis['primary_theme'])
                                })
                        except json.JSONDecodeError:
                            # If JSON parsing fails, try to extract key information
                            analysis['summary'] = claude_text[:500]
                            logger.warning("Could not parse Claude response as JSON")
                        
                        logger.info("✅ Claude analysis completed")
                        
                    except Exception as e:
                        logger.error(f"Claude analysis error: {e}")
                        analysis['summary'] = "AI analysis failed. Please check the logs."
                else:
                    if not claude_client:
                        analysis['summary'] = "Claude not configured. Enable AI analysis in settings."
                    elif not extracted_text:
                        analysis['summary'] = "Could not extract text from PDF."
                
                # Create Notion entry if available
                notion_page_id = None
                if notion_client and os.getenv('NOTION_DATABASE_ID'):
                    try:
                        # Create the Notion page
                        notion_response = notion_client.pages.create(
                            parent={"database_id": os.getenv('NOTION_DATABASE_ID')},
                            properties={
                                "Title": {"title": [{"text": {"content": analysis['title']}}]},
                                "Theme": {"select": {"name": analysis.get('suggested_theme', analysis['primary_theme'])}},
                                "Status": {"select": {"name": "Draft"}},
                                "Summary": {"rich_text": [{"text": {"content": analysis['summary'][:2000]}}]},  # Notion limit
                                "Notes": {"rich_text": [{"text": {"content": request.form.get('notes', '')}}]},
                                "Key Findings": {"rich_text": [{"text": {"content": '\n'.join(analysis.get('key_concepts', []))[:2000]}}]},
                                "Research Gaps": {"rich_text": [{"text": {"content": analysis.get('research_gaps', '')[:2000]}}]},
                                "PDF Link": {"url": f"/uploads/{filename}"}  # You'd need to implement this route
                            }
                        )
                        notion_page_id = notion_response['id']
                        logger.info(f"✅ Created Notion entry: {notion_page_id}")
                        
                    except Exception as e:
                        logger.error(f"Notion creation error: {e}")
                
                # Send Discord notification if available
                if discord_client:
                    try:
                        # Create a rich embed for Discord
                        embed = {
                            "title": f"📄 New Paper Uploaded: {analysis['title'][:100]}",
                            "description": analysis['summary'][:500],
                            "color": 5814783,  # Blue color
                            "fields": [
                                {
                                    "name": "🏷️ Theme",
                                    "value": analysis.get('suggested_theme', analysis['primary_theme']),
                                    "inline": True
                                },
                                {
                                    "name": "📊 Status",
                                    "value": "Draft",
                                    "inline": True
                                },
                                {
                                    "name": "🔍 Key Concepts",
                                    "value": ', '.join(analysis.get('key_concepts', [])[:3]) or "None identified",
                                    "inline": False
                                }
                            ],
                            "footer": {
                                "text": f"Uploaded by Research Assistant"
                            },
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        if notion_page_id:
                            embed["fields"].append({
                                "name": "📝 Notion",
                                "value": "Entry created successfully",
                                "inline": True
                            })
                        
                        response = requests.post(
                            discord_client.webhook_url,
                            json={"embeds": [embed]}
                        )
                        
                        if response.status_code == 204:
                            logger.info("✅ Discord notification sent")
                        else:
                            logger.error(f"Discord notification failed: {response.status_code}")
                            
                    except Exception as e:
                        logger.error(f"Discord notification error: {e}")
                
                # Return the analysis results
                return jsonify({
                    'success': True,
                    'analysis': analysis,
                    'services_used': {
                        'pdf_extracted': bool(extracted_text),
                        'claude_analyzed': services.get('claude', False) and bool(analysis.get('key_concepts')),
                        'notion_created': bool(notion_page_id),
                        'discord_notified': services.get('discord', False)
                    }
                })
                
            except Exception as e:
                logger.error(f"Upload processing error: {e}")
                return jsonify({'error': f'Processing failed: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Please upload a PDF file'}), 400
            
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)