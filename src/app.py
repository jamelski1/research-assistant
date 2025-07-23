from flask import Flask, render_template, jsonify
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('config/api_keys.env')

app = Flask(__name__, 
            template_folder='../web/templates',
            static_folder='../web/static')

@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "message": "PhD Research Assistant is active"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
