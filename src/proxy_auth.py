from playwright.async_api import async_playwright
import logging

class EZProxyAuthenticator:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.logger = logging.getLogger(__name__)
        
    async def get_authenticated_content(self, target_url):
        """Access paywalled content through EZProxy"""
        proxied_url = f"{self.base_url}/login?url={target_url}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate to proxy login
                await page.goto(proxied_url)
                
                # Fill login form (adjust selectors for UMBC)
                await page.fill('input[name="user"]', self.username)
                await page.fill('input[name="pass"]', self.password)
                await page.click('input[type="submit"]')
                
                # Wait for redirect to target content
                await page.wait_for_load_state('networkidle')
                
                # Extract content
                content = await page.content()
                
                # For PDFs, get the download URL
                if 'pdf' in page.url:
                    pdf_url = page.url
                    # Download logic here
                    
                return {
                    'success': True,
                    'content': content,
                    'url': page.url
                }
                
            except Exception as e:
                self.logger.error(f"EZProxy authentication failed: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
            finally:
                await browser.close()