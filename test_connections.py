import os
import sys
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv('config/api_keys.env')

print("🧪 Testing Research Assistant Connections\n")
print("=" * 50)

# Test 1: Check environment variables
print("\n1️⃣ Checking API keys...")
keys = {
    'NOTION_API_KEY': 'Notion',
    'NOTION_DATABASE_ID': 'Notion Database', 
    'DISCORD_WEBHOOK_URL': 'Discord',
    'ANTHROPIC_API_KEY': 'Claude'
}

all_set = True
for key, name in keys.items():
    value = os.getenv(key)
    if value and 'YOUR_' not in value and value.strip():
        # Don't print the actual key for security
        print(f"✅ {name} key is set ({len(value)} characters)")
    else:
        print(f"❌ {name} key is missing or has placeholder")
        all_set = False

if not all_set:
    print("\n⚠️  Please set all API keys in config/api_keys.env")
    print("\nMissing keys? Here's where to get them:")
    print("- Notion: https://www.notion.so/my-integrations")
    print("- Discord: Server Settings → Integrations → Webhooks")
    print("- Claude: https://console.anthropic.com/")
    sys.exit(1)

# Test 2: Discord
print("\n2️⃣ Testing Discord...")
try:
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    response = requests.post(webhook_url, json={
        "content": "🎉 Research Assistant connected successfully!",
        "embeds": [{
            "title": "System Status",
            "description": "All systems operational",
            "color": 5814783,
            "fields": [
                {"name": "Status", "value": "✅ Online", "inline": True},
                {"name": "Version", "value": "1.0.0", "inline": True}
            ]
        }]
    })
    if response.status_code == 204:
        print("✅ Discord message sent! Check your Discord channel.")
    else:
        print(f"❌ Discord failed with status code: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Discord error: {str(e)}")

# Test 3: Notion
print("\n3️⃣ Testing Notion...")
try:
    from notion_client import Client
    
    notion = Client(auth=os.getenv('NOTION_API_KEY'))
    database_id = os.getenv('NOTION_DATABASE_ID')
    
    # Try to retrieve the database
    db = notion.databases.retrieve(database_id=database_id)
    db_title = "Unknown"
    if 'title' in db and len(db['title']) > 0:
        db_title = db['title'][0]['plain_text']
    
    print(f"✅ Connected to Notion database: '{db_title}'")
    
    # Show database properties
    print("   Database properties:")
    for prop_name in list(db.get('properties', {}).keys())[:5]:
        print(f"   - {prop_name}")
        
except Exception as e:
    print(f"❌ Notion error: {str(e)}")
    if "unauthorized" in str(e).lower():
        print("   → Make sure you've shared the database with your integration")
    elif "not found" in str(e).lower():
        print("   → Check that your database ID is correct")

# Test 4: Claude
print("\n4️⃣ Testing Claude...")
try:
    from anthropic import Anthropic
    
    # Create client with just the API key
    client = Anthropic(
        api_key=os.getenv('ANTHROPIC_API_KEY')
    )
    
    # Test with a simple message
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=50,
        messages=[{
            "role": "user", 
            "content": "Reply with: 'Research Assistant Ready!'"
        }]
    )
    
    result = response.content[0].text
    print(f"✅ Claude says: {result}")
    
except ImportError:
    print("❌ Anthropic package not installed properly")
    print("   Run: pip install --upgrade anthropic")
except Exception as e:
    error_msg = str(e)
    print(f"❌ Claude error: {error_msg}")
    
    if "api_key" in error_msg.lower():
        print("   → Check your API key format (should start with 'sk-ant-')")
    elif "credit" in error_msg.lower():
        print("   → You may need to add credits to your Anthropic account")
    elif "invalid" in error_msg.lower():
        print("   → Your API key might be incorrect")

# Summary
print("\n" + "=" * 50)
print("📊 Connection Summary:")
print("=" * 50)

# We'll check what worked
services_status = {
    "Discord": "Check above",
    "Notion": "Check above", 
    "Claude": "Check above"
}

print("\nIf all services show ✅, your Research Assistant is ready!")
print("If any show ❌, check the error messages above.")

print("\n💡 Next steps:")
print("1. Fix any ❌ connections")
print("2. Create your first research entry")
print("3. Set up automated updates")