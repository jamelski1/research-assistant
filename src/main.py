import os
import json
import logging
import requests
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from flask import send_from_directory


# Set up logger
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Create app
app = Flask(__name__,
            template_folder='../web/templates',
            static_folder='../web/static')
app.config['UPLOAD_FOLDER'] = '../data/cache'

# Track which services initialize successfully
services = {
    'notion': False,
    'discord': False,
    'claude': False
}

# Initialize Notion
notion_client = None
if os.getenv('NOTION_API_KEY') and 'YOUR_' not in os.getenv('NOTION_API_KEY', ''):
    try:
        from notion_client import Client
        notion_client = Client(auth=os.getenv('NOTION_API_KEY'))
        services['notion'] = True
        logger.info("✅ Notion client initialized")
    except Exception as e:
        logger.error(f"Notion setup failed: {e}")

# Initialize Discord
discord_client = None
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
claude_client = None
if os.getenv('ANTHROPIC_API_KEY') and 'YOUR_' not in os.getenv('ANTHROPIC_API_KEY', ''):
    try:
        from anthropic import Anthropic
        claude_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        services['claude'] = True
        logger.info("✅ Claude client initialized")
    except Exception as e:
        logger.error(f"Claude setup failed: {e}")

NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

def save_summary_to_notion(summary, pdf_filename, notes=None, external_link=None):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    pdf_url = external_link if external_link else f"http://127.0.0.1:5000/uploads/{pdf_filename}"

    payload = {
        "parent": { "database_id": NOTION_DATABASE_ID },
        "properties": {
            "Title": {
                "title": [{"text": {"content": summary.get("title", pdf_filename)}}]
            },
            "Summary": {
                "rich_text": [{"text": {"content": summary.get("summary", "")}}]
            },
            "Key Findings": {
                "rich_text": [{"text": {"content": summary.get("key_findings", "")}}]
            },
            "Research Gaps": {
                "rich_text": [{"text": {"content": summary.get("research_gaps", "")}}]
            },
            "PDF Link": {
                "url": pdf_url
            },
            "Status": {
                "select": {"name": "New"}
            },
        }
    }

    if notes:
        payload["properties"]["Notes"] = {
            "rich_text": [{"text": {"content": notes}}]
        }

    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)

    if response.status_code != 200:
        raise Exception(f"Notion creation error: {response.text}")

    notion_url = response.json().get("url")
    return notion_url

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/dashboard')
def dashboard():
    if not notion_client or not os.getenv('NOTION_DATABASE_ID'):
        return render_template('dashboard.html', papers=[])

    try:
        database_id = os.getenv('NOTION_DATABASE_ID')
        notion_response = notion_client.databases.query(database_id=database_id)
        results = notion_response.get("results", [])

        papers = []
        for page in results:
            props = page["properties"]

            papers.append({
                "id": page["id"],  # Add this line to include page ID
                "title": props["Title"]["title"][0]["text"]["content"] if props["Title"]["title"] else "Untitled",
                "summary": props["Summary"]["rich_text"][0]["text"]["content"] if props["Summary"]["rich_text"] else "",
                "theme": props["Theme"]["select"]["name"] if props["Theme"].get("select") else "",
                "status": props["Status"]["select"]["name"] if props.get("Status") and props["Status"].get("select") else "",
                "pdf_link": props["PDF Link"]["url"] if props.get("PDF Link") else "#",
                "last_updated": page.get("last_edited_time", "")[:10]
            })

        return render_template('dashboard.html', papers=papers)

    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return render_template('dashboard.html', papers=[])


def extract_text_from_url(url):
    """Extract text content from a URL"""
    try:
        # Set headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Fetch the content
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        # Try to extract title
        title = ""
        if soup.title:
            title = soup.title.string
        elif soup.find('h1'):
            title = soup.find('h1').get_text()

        return {
            'text': text,
            'title': title,
            'url': url,
            'success': True
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return {
            'text': '',
            'title': '',
            'url': url,
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        return {
            'text': '',
            'title': '',
            'url': url,
            'success': False,
            'error': str(e)
        }


def extract_text_from_pdf_url(url):
    """Download and extract text from a PDF URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Download PDF
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Save temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        # Extract text using PyPDF2
        import PyPDF2
        extracted_text = ""
        with open(tmp_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
            pages_to_read = min(num_pages, 10)

            for page_num in range(pages_to_read):
                page = pdf_reader.pages[page_num]
                extracted_text += page.extract_text() + "\n"

        # Clean up temp file
        os.unlink(tmp_path)

        return {
            'text': extracted_text,
            'pages': num_pages,
            'success': True
        }

    except Exception as e:
        logger.error(f"Error processing PDF URL {url}: {e}")
        return {
            'text': '',
            'pages': 0,
            'success': False,
            'error': str(e)
        }


@app.route('/upload', methods=['GET', 'POST'])
def upload_paper():
    if request.method == 'POST':
        file = request.files.get('file')
        external_link = request.form.get('external_link', '').strip()

        if not file and not external_link:
            return jsonify({'error': 'Please upload a PDF or provide an external link'}), 400

        filename = ""
        extracted_text = ""
        num_pages = 0
        link_title = ""

        # Handle uploaded PDF
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            logger.info(f"File uploaded: {filename}")

            try:
                import PyPDF2
                with open(filepath, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    num_pages = len(pdf_reader.pages)
                    pages_to_read = min(num_pages, 10)
                    for page_num in range(pages_to_read):
                        page = pdf_reader.pages[page_num]
                        extracted_text += page.extract_text() + "\n"

                logger.info(f"Extracted {len(extracted_text)} characters from {pages_to_read} pages")
            except Exception as e:
                logger.error(f"PDF extraction error: {e}")
                extracted_text = ""

        # Handle external link
        elif external_link:
            logger.info(f"Processing external link: {external_link}")

            # Check if it's a PDF link
            if external_link.lower().endswith('.pdf') or 'pdf' in external_link.lower():
                pdf_result = extract_text_from_pdf_url(external_link)
                if pdf_result['success']:
                    extracted_text = pdf_result['text']
                    num_pages = pdf_result.get('pages', 0)
                    filename = f"external_pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    logger.info(f"Extracted {len(extracted_text)} characters from PDF URL")
                else:
                    logger.error(f"Failed to extract PDF from URL: {pdf_result.get('error')}")
            else:
                # Regular webpage
                web_result = extract_text_from_url(external_link)
                if web_result['success']:
                    extracted_text = web_result['text']
                    link_title = web_result['title']
                    filename = f"web_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    logger.info(f"Extracted {len(extracted_text)} characters from webpage")
                else:
                    logger.error(f"Failed to extract text from URL: {web_result.get('error')}")

        # Initialize analysis
        analysis = {
            'title': link_title or filename.replace('.pdf', '').replace('.txt', ''),
            'summary': 'Processing...',
            'key_concepts': [],
            'research_gaps': '',
            'methodology': '',
            'primary_theme': request.form.get('theme', 'General'),
            'filename': filename,
            'pages': num_pages,
            'extraction_success': bool(extracted_text),
            'source_type': 'pdf' if filename.endswith('.pdf') else 'web',
            'source_url': external_link if external_link else None
        }

        # Claude analysis (same as before but with updated prompt)
        if claude_client and extracted_text:
            try:
                # Adjust prompt based on source type
                source_info = "Paper text" if analysis['source_type'] == 'pdf' else "Web content"

                prompt = f"""You are an expert research assistant helping with a PhD in Information Systems 
focusing on AI, LLM hallucinations, developer workflows, and quality assurance.

Analyze this {'academic paper' if analysis['source_type'] == 'pdf' else 'research content'} and provide:
1. A concise title (if you can identify it)
2. A 2-3 sentence summary
3. 3-5 key concepts or contributions
4. Research gaps or limitations identified
5. The primary research methodology used (if applicable)
6. Which theme it best fits: AI, LLM Hallucinations, Developer Workflows, QA, or General

{source_info}:
{extracted_text[:8000]}

Respond in JSON format with keys: title, summary, key_concepts (array), research_gaps, methodology, suggested_theme"""

                response = claude_client.messages.create(
                    model="claude-3-opus-20240229",
                    max_tokens=1000,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                )

                # Rest of Claude processing remains the same...
                import re
                claude_text = response.content[0].text
                json_match = re.search(r'\{.*\}', claude_text, re.DOTALL)
                if json_match:
                    claude_analysis = json.loads(json_match.group())
                    analysis.update({
                        'title': claude_analysis.get('title', analysis['title']),
                        'summary': claude_analysis.get('summary', 'No summary available'),
                        'key_concepts': claude_analysis.get('key_concepts', []),
                        'research_gaps': claude_analysis.get('research_gaps', ''),
                        'methodology': claude_analysis.get('methodology', ''),
                        'suggested_theme': claude_analysis.get('suggested_theme', analysis['primary_theme'])
                    })
                else:
                    analysis['summary'] = claude_text[:500]
                    logger.warning("Could not parse Claude response as JSON")

                logger.info("✅ Claude analysis completed")
            except Exception as e:
                logger.error(f"Claude analysis error: {e}")
                analysis['summary'] = "AI analysis failed."
        elif not extracted_text:
            analysis['summary'] = "No text could be extracted from the provided source."

        # Save to Notion (update the function call to include source type)
        notion_page_url = None
        if services['notion']:
            # Include source type in Notion entry
            notes = request.form.get('notes', '')
            if external_link:
                notes = f"Source: {external_link}\nType: {analysis['source_type']}\n\n{notes}"

            notion_page_url = save_summary_to_notion(
                analysis,
                filename,
                notes,
                external_link
            )

        # Run gap-filling search if we have research gaps
        if analysis.get('research_gaps') and services.get('claude'):
            try:
                from research_agent import ResearchGapAgent

                agent = ResearchGapAgent(
                    claude_client=claude_client,
                    notion_client=notion_client,
                    discord_client=discord_client
                )

                # Run the async search
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                gap_results = loop.run_until_complete(
                    agent.find_papers_for_gaps(
                        research_gaps=analysis['research_gaps'],
                        key_concepts=analysis.get('key_concepts', []),
                        original_title=analysis['title']
                    )
                )

                # Add to response
                analysis['gap_filling_papers'] = gap_results['papers'][:5]
                analysis['gap_filling_summary'] = gap_results['summary']

                # Notify Discord if enabled
                if discord_client:
                    agent.notify_discord_recommendations(gap_results, analysis['title'])

                logger.info(f"Found {len(gap_results['papers'])} gap-filling papers")

            except Exception as e:
                logger.error(f"Gap-filling search error: {e}")

        # Discord notification
        if discord_client and services['discord']:
            try:
                embed = {
                    "title": f"📄 New {'Paper' if analysis['source_type'] == 'pdf' else 'Content'} Analyzed: {analysis['title'][:100]}",
                    "description": analysis['summary'][:500],
                    "color": 5814783,
                    "fields": [
                        {
                            "name": "🏷️ Theme",
                            "value": analysis.get('suggested_theme', analysis['primary_theme']),
                            "inline": True
                        },
                        {
                            "name": "📊 Source",
                            "value": analysis['source_type'].upper(),
                            "inline": True
                        },
                        {
                            "name": "🔍 Key Concepts",
                            "value": ', '.join(analysis.get('key_concepts', [])[:3]) or "None identified",
                            "inline": False
                        }
                    ],
                    "timestamp": datetime.now().isoformat()
                }

                if external_link:
                    embed["url"] = external_link

                response = requests.post(
                    discord_client.webhook_url,
                    json={"embeds": [embed]}
                )

                if response.status_code == 204:
                    logger.info("✅ Discord notification sent")

            except Exception as e:
                logger.error(f"Discord notification error: {e}")

        return jsonify({
            'success': True,
            'analysis': analysis,
            'services_used': {
                'pdf_extracted': bool(extracted_text),
                'claude_analyzed': services.get('claude', False) and bool(analysis.get('key_concepts')),
                'notion_created': bool(notion_page_url),
                'notion_url': notion_page_url,
                'discord_notified': services.get('discord', False)
            }
        })

    return render_template('upload.html')


@app.route('/api/find-gap-papers', methods=['POST'])
def find_gap_papers():
    """Find papers to fill research gaps for a specific entry"""
    data = request.json
    research_gaps = data.get('research_gaps')
    key_concepts = data.get('key_concepts', [])
    title = data.get('title', 'Unknown')

    if not research_gaps:
        return jsonify({'error': 'No research gaps provided'}), 400

    try:
        from research_agent import ResearchGapAgent

        agent = ResearchGapAgent(
            claude_client=claude_client,
            notion_client=notion_client,
            discord_client=discord_client
        )

        # Run the async search
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        results = loop.run_until_complete(
            agent.find_papers_for_gaps(
                research_gaps=research_gaps,
                key_concepts=key_concepts,
                original_title=title
            )
        )

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        logger.error(f"Gap analysis error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze-all-gaps', methods=['POST'])
def analyze_all_gaps():
    """Analyze all papers in Notion database for research gaps and automatically add one paper per gap"""

    if not notion_client or not os.getenv('NOTION_DATABASE_ID'):
        return jsonify({'error': 'Notion not configured'}), 400

    try:
        # Get all papers from Notion with research gaps
        database_id = os.getenv('NOTION_DATABASE_ID')
        notion_response = notion_client.databases.query(
            database_id=database_id,
            filter={
                "property": "Research Gaps",
                "rich_text": {
                    "is_not_empty": True
                }
            }
        )

        results = notion_response.get("results", [])
        findings = []
        papers_analyzed = 0
        papers_added = 0

        logger.info(f"Found {len(results)} papers with research gaps to analyze")

        for page in results[:3]:  # Limit to 3 papers per run
            props = page["properties"]

            # Extract paper details
            title = props["Title"]["title"][0]["text"]["content"] if props["Title"]["title"] else "Untitled"
            research_gaps = props["Research Gaps"]["rich_text"][0]["text"]["content"] if props["Research Gaps"][
                "rich_text"] else ""
            theme = props["Theme"]["select"]["name"] if props.get("Theme") and props["Theme"].get(
                "select") else "General"

            # Extract key concepts
            key_concepts = []
            if props.get("Key Findings") and props["Key Findings"]["rich_text"]:
                concepts_text = props["Key Findings"]["rich_text"][0]["text"]["content"]
                key_concepts = [c.strip() for c in concepts_text.split('\n') if c.strip()][:5]

            if research_gaps:
                logger.info(f"Analyzing gaps for: {title}")
                papers_analyzed += 1

                try:
                    from research_agent import ResearchGapAgent
                    agent = ResearchGapAgent(
                        claude_client=claude_client,
                        notion_client=notion_client,
                        discord_client=discord_client
                    )

                    # Run the async search
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    gap_results = loop.run_until_complete(
                        agent.find_papers_for_gaps(
                            research_gaps=research_gaps,
                            key_concepts=key_concepts,
                            original_title=title
                        )
                    )

                    # If papers found, add the best one to Notion
                    if gap_results['papers']:
                        best_paper = gap_results['papers'][0]  # First paper is most relevant

                        # Fetch the paper content
                        paper_content = loop.run_until_complete(
                            agent.fetch_and_analyze_paper(best_paper['url'])
                        )

                        if paper_content['success']:
                            # Add to Notion
                            new_paper_url = agent.add_paper_to_notion(
                                paper_data=paper_content,
                                original_paper_title=title,
                                theme=theme,
                                source_paper_gaps=research_gaps
                            )

                            if new_paper_url:
                                papers_added += 1
                                findings.append({
                                    'title': title[:50] + '...' if len(title) > 50 else title,
                                    'papers_found': len(gap_results['papers']),
                                    'paper_added': best_paper['title'][:80],
                                    'notion_url': new_paper_url,
                                    'summary': f'Added: {best_paper["title"][:60]}...'
                                })

                                # Send Discord notification
                                if discord_client:
                                    agent.notify_paper_added(
                                        original_title=title,
                                        new_paper=best_paper,
                                        notion_url=new_paper_url
                                    )
                            else:
                                findings.append({
                                    'title': title[:50],
                                    'papers_found': len(gap_results['papers']),
                                    'paper_added': None,
                                    'summary': 'Found papers but failed to add to Notion'
                                })
                        else:
                            findings.append({
                                'title': title[:50],
                                'papers_found': len(gap_results['papers']),
                                'paper_added': None,
                                'summary': 'Could not fetch paper content'
                            })
                    else:
                        findings.append({
                            'title': title[:50],
                            'papers_found': 0,
                            'paper_added': None,
                            'summary': 'No relevant papers found'
                        })

                except Exception as e:
                    logger.error(f"Error analyzing gaps for {title}: {e}")
                    findings.append({
                        'title': title[:50],
                        'papers_found': 0,
                        'paper_added': None,
                        'summary': f'Error: {str(e)}'
                    })

        return jsonify({
            'success': True,
            'papers_analyzed': papers_analyzed,
            'papers_added': papers_added,
            'findings': findings
        })

    except Exception as e:
        logger.error(f"Gap analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/fetch-new-paper', methods=['POST'])
def fetch_new_paper():
    # This assumes you're pulling the latest paper added to your DB or source
    new_paper = get_latest_added_paper()  # <-- you'll need to define this logic

    if not new_paper:
        return jsonify({"html": ""})

    # Call the method with actual data
    result = agent.find_papers_for_gaps(
        research_gaps=new_paper.get('research_gaps', ''),
        key_concepts=new_paper.get('key_concepts', []),
        original_title=new_paper.get('title', '')
    )

    # Render it to HTML
    html = render_template("partials/paper_card.html", paper=result)
    return jsonify({"html": html})

@app.route('/api/delete-paper/<page_id>', methods=['DELETE'])
def delete_paper(page_id):
    """Delete a paper from Notion database"""
    
    if not notion_client:
        return jsonify({'error': 'Notion not configured'}), 400
    
    try:
        # Archive the page in Notion (soft delete)
        notion_client.pages.update(
            page_id=page_id,
            archived=True
        )
        
        logger.info(f"Deleted paper with ID: {page_id}")
        
        # Optionally notify Discord
        if discord_client:
            try:
                discord_client.send_message(f"🗑️ Paper deleted from database")
            except:
                pass
        
        return jsonify({
            'success': True,
            'message': 'Paper deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Failed to delete paper {page_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent-status', methods=['GET'])
def get_agent_status():
    """Get current agent status"""
    # In a real implementation, you'd track this in a database or cache
    return jsonify({
        'running': False,
        'last_run': None,
        'interval_minutes': 60
    })
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
