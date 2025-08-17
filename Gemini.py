# ------------------------------
# Gemini AI - With Authentication & Database (English Version)
# ------------------------------

from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session, flash
import google.generativeai as genai
import requests
import markdown
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
import os
import re

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Random secret key for sessions

# Database setup
DATABASE = 'gemini_app.db'

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add new columns if they don't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN google_api_key TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN serpapi_key TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN last_login TIMESTAMP')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Chat sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            title TEXT NOT NULL,
            messages TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    """Hash password with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password, stored_hash):
    """Verify password against stored hash"""
    try:
        salt, hash_part = stored_hash.split(':')
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash == hash_part
    except:
        return False

def login_required(f):
    """Decorator for routes that require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_api_keys(user_id):
    """Get user's API keys from database"""
    conn = get_db_connection()
    user = conn.execute('SELECT google_api_key, serpapi_key FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    
    if user:
        return {
            'google_api_key': user['google_api_key'],
            'serpapi_key': user['serpapi_key']
        }
    return {'google_api_key': None, 'serpapi_key': None}

# Available models - restricted as requested
AVAILABLE_MODELS = {
    "gemini-1.5-flash": "Gemini 1.5 Flash",
    "gemini-2.0-flash": "Gemini 2.0 Flash",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-pro": "Gemini 2.5 Pro"
}

def should_search_internet(user_input):
    """Determine if the user input requires internet search"""
    search_keywords = [
        'search', 'find', 'look up', 'what\'s happening', 'latest', 'recent', 'current', 'today',
        'news', 'weather', 'stock', 'price', 'update', 'information about', 'tell me about',
        'what is happening', 'חפש', 'מצא', 'חדשות', 'מזג אוויר', 'מה קורה', 'עדכונים'
    ]
    
    user_input_lower = user_input.lower()
    
    # Check for explicit search keywords
    for keyword in search_keywords:
        if keyword in user_input_lower:
            return True
    
    # Check for question patterns that might need current info
    question_patterns = [
        r'what.*happening',
        r'what.*today',
        r'latest.*',
        r'current.*',
        r'recent.*',
        r'how much.*cost',
        r'price of.*',
        r'weather in.*'
    ]
    
    for pattern in question_patterns:
        if re.search(pattern, user_input_lower):
            return True
    
    return False

def serpapi_search(query, api_key):
    """Search the web using SerpAPI"""
    if not api_key:
        return "Web search unavailable - please set SerpAPI key in settings"
    
    try:
        url = "https://serpapi.com/search"
        params = {
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "num": 5,
            "hl": "en",
            "gl": "us"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = ""
        organic_results = data.get("organic_results", [])
        
        if not organic_results:
            return "No relevant results found for this search."
            
        for i, item in enumerate(organic_results[:5], 1):
            title = item.get('title', 'No title')
            link = item.get('link', '#')
            snippet = item.get('snippet', 'No description')
            
            results += f"**{i}. {title}**\n"
            results += f"🔗 {link}\n"
            results += f"📝 {snippet}\n\n"
                
        return results
        
    except Exception as e:
        return f"Search error: {str(e)}"

def generate_ai_response(user_input, search_results, model, api_key, searched_internet=False):
    """Generate AI response using Gemini"""
    if not api_key:
        return "Please set up Google API key in settings to use Gemini"
    
    try:
        genai.configure(api_key=api_key)
        
        if searched_internet and search_results:
            prompt = f"""
You are a smart and helpful AI assistant named Gemini. Answer in a friendly and professional manner.
Use the search results below to provide accurate and up-to-date answers.
You were created by xd-AI and you are based on a large language model trained by Google.

User question: "{user_input}"

Web search results:
{search_results}

Response guidelines:
1. Answer clearly and understandably
2. Use information from search results if relevant
3. Add relevant emojis to your response
4. If there are multiple sources, summarize them in an organized way
5. Be friendly and helpful
6. You speak in a humorous way in every conversation, every response, and every help you provide
7. You speak hebrew and english - if user speaks english respond in english, if hebrew respond in hebrew!
8. You can Search in internet.
"""
        else:
            prompt = f"""
You are a smart and helpful AI assistant named Gemini. Answer in a friendly and professional manner.
You were created by xd-AI and you are based on a large language model trained by Google.

User question: "{user_input}"

Response guidelines:
1. Answer clearly and understandably based on your knowledge
2. Add relevant emojis to your response
3. Be friendly and helpful
4. You speak in a humorous way in every conversation, every response, and every help you provide
5. You speak hebrew and english - if user speaks english respond in english, if hebrew respond in hebrew!
6. If you think current/real-time information would be helpful, mention that the user can ask you to search for it.
7. You can Search in internet.
8. You Speak in a humrous way in every conversation, every response, and every help you provide.
9. You become a software engineer!!:
- You can write a code
- You help with programing
- You can help with software development
- You can help with AI development
- You can help with NLP and languange models development
- You can help with web development
- You can help with automation bots and softwares development.
10. You can help with anything.!
11. You can help to learn!
- You can help with math
- You can help with hebrew
- You can help with chemistry
- You can help with physics
- You can help with biology
- You can help with english
- You can help with Science
12. You speak english if user speak english
13. You speak hebrew if user speak hebrew
"""
        
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Sorry, an error occurred while generating the response: {str(e)}"

# HTML Templates
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Gemini AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .auth-container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 400px;
            padding: 40px;
            text-align: center;
        }

        .logo {
            width: 64px;
            height: 64px;
            background: linear-gradient(135deg, #1a73e8, #34a853);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            color: white;
            margin: 0 auto 24px;
            position: relative;
        }

        .logo::before {
            content: '✦';
            position: absolute;
            animation: rotate 4s linear infinite;
        }

        @keyframes rotate {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        h1 {
            font-size: 28px;
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 8px;
        }

        .subtitle {
            color: #6b7280;
            margin-bottom: 32px;
            font-size: 14px;
        }

        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #374151;
            font-size: 14px;
        }

        .form-group input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s ease;
            direction: ltr;
            text-align: left;
        }

        .form-group input:focus {
            outline: none;
            border-color: #1a73e8;
        }

        .submit-btn {
            width: 100%;
            background: linear-gradient(135deg, #1a73e8, #34a853);
            color: white;
            border: none;
            padding: 14px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease;
            margin-bottom: 20px;
        }

        .submit-btn:hover {
            transform: translateY(-2px);
        }

        .flash-messages {
            margin-bottom: 20px;
        }

        .flash-message {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }

        .flash-error {
            background: #fef2f2;
            color: #dc2626;
            border: 1px solid #fecaca;
        }

        .flash-success {
            background: #f0fdf4;
            color: #16a34a;
            border: 1px solid #bbf7d0;
        }

        .tabs {
            display: flex;
            margin-bottom: 30px;
            background: #f3f4f6;
            border-radius: 8px;
            padding: 4px;
        }

        .tab {
            flex: 1;
            padding: 12px;
            background: transparent;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s ease;
        }

        .tab.active {
            background: white;
            color: #1a73e8;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="logo"></div>
        <h1>Welcome</h1>
        <p class="subtitle">Login or register to start using Gemini AI</p>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('login')">Login</button>
            <button class="tab" onclick="switchTab('register')">Register</button>
        </div>
        
        <!-- Login Form -->
        <form id="loginForm" method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label for="login_email">Email:</label>
                <input type="email" id="login_email" name="email" required>
            </div>
            <div class="form-group">
                <label for="login_password">Password:</label>
                <input type="password" id="login_password" name="password" required>
            </div>
            <button type="submit" class="submit-btn">Login</button>
        </form>
        
        <!-- Register Form -->
        <form id="registerForm" method="POST" action="{{ url_for('register') }}" style="display: none;">
            <div class="form-group">
                <label for="register_username">Username:</label>
                <input type="text" id="register_username" name="username" required>
            </div>
            <div class="form-group">
                <label for="register_email">Email:</label>
                <input type="email" id="register_email" name="email" required>
            </div>
            <div class="form-group">
                <label for="register_password">Password:</label>
                <input type="password" id="register_password" name="password" required minlength="6">
            </div>
            <div class="form-group">
                <label for="register_confirm">Confirm Password:</label>
                <input type="password" id="register_confirm" name="confirm_password" required>
            </div>
            <button type="submit" class="submit-btn">Register</button>
        </form>
    </div>

    <script>
        function switchTab(tab) {
            const tabs = document.querySelectorAll('.tab');
            const loginForm = document.getElementById('loginForm');
            const registerForm = document.getElementById('registerForm');
            
            tabs.forEach(t => t.classList.remove('active'));
            
            if (tab === 'login') {
                tabs[0].classList.add('active');
                loginForm.style.display = 'block';
                registerForm.style.display = 'none';
            } else {
                tabs[1].classList.add('active');
                loginForm.style.display = 'none';
                registerForm.style.display = 'block';
            }
        }
        
        document.getElementById('registerForm').addEventListener('submit', function(e) {
            const password = document.getElementById('register_password').value;
            const confirm = document.getElementById('register_confirm').value;
            
            if (password !== confirm) {
                e.preventDefault();
                alert('Passwords do not match');
            }
        });
    </script>
</body>
</html>
"""

SETTINGS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Settings - Gemini AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', sans-serif;
            background: #0d1117;
            color: #ececec;
            min-height: 100vh;
            padding: 20px;
        }

        .settings-container {
            max-width: 600px;
            margin: 0 auto;
            background: #171717;
            border-radius: 12px;
            padding: 32px;
            border: 1px solid #2e2f34;
        }

        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 32px;
            padding-bottom: 16px;
            border-bottom: 1px solid #2e2f34;
        }

        .header h1 {
            font-size: 24px;
            font-weight: 600;
        }

        .back-btn {
            background: #202123;
            border: 1px solid #2e2f34;
            color: #ececec;
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.15s ease;
        }

        .back-btn:hover {
            background: #2e2f34;
        }

        .section {
            margin-bottom: 32px;
        }

        .section-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
            color: #ececec;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #ececec;
            font-size: 14px;
        }

        .form-group input {
            width: 100%;
            padding: 12px 16px;
            background: #202123;
            border: 1px solid #2e2f34;
            border-radius: 8px;
            color: #ececec;
            font-size: 14px;
            transition: border-color 0.3s ease;
            direction: ltr;
            text-align: left;
        }

        .form-group input:focus {
            outline: none;
            border-color: #1a73e8;
        }

        .submit-btn {
            background: linear-gradient(135deg, #1a73e8, #34a853);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease;
        }

        .submit-btn:hover {
            transform: translateY(-1px);
        }

        .logout-btn {
            background: #ef4444;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s ease;
            text-decoration: none;
            display: inline-block;
        }

        .logout-btn:hover {
            background: #dc2626;
        }

        .flash-messages {
            margin-bottom: 20px;
        }

        .flash-message {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }

        .flash-error {
            background: #2d1b1b;
            color: #f87171;
            border: 1px solid #3f2626;
        }

        .flash-success {
            background: #1a2e1a;
            color: #4ade80;
            border: 1px solid #2d4a2d;
        }

        .help-text {
            font-size: 12px;
            color: #8e8ea0;
            margin-top: 4px;
            line-height: 1.4;
        }

        .api-status {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
            font-size: 12px;
        }

        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .status-active {
            background: #4ade80;
        }

        .status-inactive {
            background: #ef4444;
        }
    </style>
</head>
<body>
    <div class="settings-container">
        <div class="header">
            <h1>Settings</h1>
            <a href="{{ url_for('index') }}" class="back-btn">
                <i class="fas fa-arrow-left"></i>
                Back to Chat
            </a>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <div class="section">
            <h2 class="section-title">API Keys</h2>
            <form method="POST" action="{{ url_for('settings') }}">
                <div class="form-group">
                    <label for="google_api_key">Google Gemini API Key:</label>
                    <input type="password" id="google_api_key" name="google_api_key" 
                           value="{{ user.google_api_key or '' }}" 
                           placeholder="Enter your Google Gemini API key">
                    <div class="help-text">
                        Get an API key from
                        <a href="https://makersuite.google.com/app/apikey" target="_blank" style="color: #1a73e8;">Google AI Studio</a>
                    </div>
                    <div class="api-status">
                        <div class="status-indicator {{ 'status-active' if user.google_api_key else 'status-inactive' }}"></div>
                        {{ 'Configured' if user.google_api_key else 'Not configured' }}
                    </div>
                </div>

                <div class="form-group">
                    <label for="serpapi_key">SerpAPI Key (for web search):</label>
                    <input type="password" id="serpapi_key" name="serpapi_key" 
                           value="{{ user.serpapi_key or '' }}" 
                           placeholder="Enter your SerpAPI key">
                    <div class="help-text">
                        Get an API key from
                        <a href="https://serpapi.com/dashboard" target="_blank" style="color: #1a73e8;">SerpAPI</a>
                        (optional - for web search)
                    </div>
                    <div class="api-status">
                        <div class="status-indicator {{ 'status-active' if user.serpapi_key else 'status-inactive' }}"></div>
                        {{ 'Configured' if user.serpapi_key else 'Not configured' }}
                    </div>
                </div>

                <button type="submit" class="submit-btn">
                    <i class="fas fa-save"></i>
                    Save Settings
                </button>
            </form>
        </div>

        <div class="section">
            <h2 class="section-title">Account</h2>
            <p style="margin-bottom: 16px; color: #8e8ea0;">
                Logged in as: <strong>{{ user.username }}</strong> ({{ user.email }})
            </p>
            <a href="{{ url_for('logout') }}" class="logout-btn">
                <i class="fas fa-sign-out-alt"></i>
                Logout
            </a>
        </div>
    </div>
</body>
</html>
"""

MAIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini AI</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github-dark.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Söhne:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --text-primary: #ececec;
            --text-secondary: #8e8ea0;
            --text-tertiary: #565869;
            --surface-primary: #0d1117;
            --surface-secondary: #171717;
            --surface-tertiary: #202123;
            --border-light: #2e2f34;
            --accent: #19c37d;
            --danger: #ef4444;
            --gemini-blue: #1a73e8;
            --gemini-green: #34a853;
            --sidebar-width: 260px;
            --search-color: #ff9500;
        }

        body {
            font-family: 'Söhne', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--surface-primary);
            color: var(--text-primary);
            font-size: 14px;
            line-height: 1.5;
        }

        .app-layout {
            display: flex;
            height: 100vh;
            width: 100vw;
        }

        .sidebar {
            width: var(--sidebar-width);
            background: var(--surface-secondary);
            display: flex;
            flex-direction: column;
            border-right: 1px solid var(--border-light);
        }

        .sidebar-header {
            padding: 12px;
            border-bottom: 1px solid var(--border-light);
        }

        .new-chat-btn {
            width: 100%;
            background: transparent;
            border: 1px solid var(--border-light);
            color: var(--text-primary);
            padding: 12px 16px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.15s ease;
        }

        .new-chat-btn:hover {
            background: var(--surface-tertiary);
        }

        .chat-history {
            flex: 1;
            overflow-y: auto;
            padding: 8px;
        }

        .sidebar-footer {
            padding: 12px;
            border-top: 1px solid var(--border-light);
        }

        .user-info {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 14px;
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
        }

        .user-details {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .user-avatar {
            width: 24px;
            height: 24px;
            background: linear-gradient(135deg, var(--gemini-blue), var(--gemini-green));
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: 600;
            color: white;
            position: relative;
            animation: geminiGlow 3s ease-in-out infinite;
        }

        .user-avatar::before {
            content: '✦';
            position: absolute;
            animation: geminiRotate 4s linear infinite;
        }

        .settings-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 6px;
            border-radius: 4px;
            transition: all 0.15s ease;
            text-decoration: none;
        }

        .settings-btn:hover {
            background: var(--surface-tertiary);
            color: var(--text-primary);
        }

        @keyframes geminiGlow {
            0%, 100% { 
                box-shadow: 0 0 15px rgba(26, 115, 232, 0.3);
                transform: scale(1);
            }
            50% { 
                box-shadow: 0 0 25px rgba(52, 168, 83, 0.5);
                transform: scale(1.05);
            }
        }

        @keyframes geminiRotate {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: var(--surface-primary);
            position: relative;
        }

        .model-selector {
            position: absolute;
            top: 16px;
            right: 16px;
            z-index: 10;
        }

        .model-dropdown {
            background: var(--surface-tertiary);
            border: 1px solid var(--border-light);
            border-radius: 8px;
            color: var(--text-primary);
            padding: 8px 12px;
            font-size: 13px;
            cursor: pointer;
            outline: none;
            transition: all 0.15s ease;
        }

        .model-dropdown:hover {
            background: var(--border-light);
        }

        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            max-width: 768px;
            margin: 0 auto;
            width: 100%;
            padding: 0 16px;
        }

        .chat-messages {
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 24px 0;
            display: flex;
            flex-direction: column;
            gap: 24px;
            min-height: 0;
            max-height: calc(100vh - 200px);
        }

        .welcome-screen {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex: 1;
            text-align: center;
            padding: 48px 24px;
            gap: 32px;
        }

        .welcome-logo {
            width: 64px;
            height: 64px;
            background: linear-gradient(135deg, var(--gemini-blue), var(--gemini-green));
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            color: white;
            position: relative;
            animation: geminiGlow 3s ease-in-out infinite;
        }

        .welcome-logo::before {
            content: '✦';
            position: absolute;
            animation: geminiRotate 4s linear infinite;
        }

        .welcome-title {
            font-size: 32px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }

        .welcome-subtitle {
            font-size: 16px;
            color: var(--text-secondary);
            margin-bottom: 32px;
        }

        .welcome-suggestions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            max-width: 600px;
            width: 100%;
        }

        .suggestion-card {
            background: var(--surface-tertiary);
            border: 1px solid var(--border-light);
            border-radius: 12px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.15s ease;
            text-align: left;
        }

        .suggestion-card:hover {
            background: var(--border-light);
            border-color: var(--text-secondary);
        }

        .suggestion-title {
            font-size: 14px;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 4px;
        }

        .suggestion-description {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.4;
        }

        .message-group {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .message {
            display: flex;
            gap: 16px;
            padding: 0;
            position: relative;
        }

        .message-avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 600;
            flex-shrink: 0;
            margin-top: 4px;
        }

        .message.user .message-avatar {
            background: var(--accent);
            color: white;
        }

        .message.user .message-avatar::before {
            content: '👤';
            font-size: 16px;
        }

        .message.assistant .message-avatar {
            background: linear-gradient(135deg, var(--gemini-blue), var(--gemini-green));
            color: white;
            position: relative;
            animation: geminiGlow 3s ease-in-out infinite;
        }

        .message.assistant .message-avatar::before {
            content: '✦';
            position: absolute;
            animation: geminiRotate 4s linear infinite;
        }

        .message-content {
            flex: 1;
            padding-top: 4px;
        }

        .message-text {
            color: var(--text-primary);
            line-height: 1.6;
            font-size: 15px;
            word-wrap: break-word;
        }

        .message.user .message-text {
            background: var(--surface-tertiary);
            padding: 12px 16px;
            border-radius: 18px;
            max-width: 70%;
            margin-left: auto;
        }

        .message.user {
            flex-direction: row-reverse;
        }

        .message.user .message-content {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }

        .message.assistant .message-text {
            padding-right: 48px;
        }

        .message-actions {
            display: flex;
            gap: 8px;
            margin-top: 8px;
            opacity: 0;
            transition: opacity 0.15s ease;
        }

        .message:hover .message-actions {
            opacity: 1;
        }

        .message-action-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 6px 8px;
            border-radius: 4px;
            font-size: 12px;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .message-action-btn:hover {
            background: var(--surface-tertiary);
            color: var(--text-primary);
        }

        .thinking-message {
            display: flex;
            gap: 16px;
            padding: 0;
            opacity: 0;
            animation: messageSlideIn 0.3s ease forwards;
        }

        .thinking-avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--gemini-blue), var(--gemini-green));
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            margin-top: 4px;
        }

        .thinking-spinner {
            width: 24px;
            height: 24px;
            background: linear-gradient(135deg, var(--gemini-blue), var(--gemini-green));
            border-radius: 50%;
            position: relative;
            animation: geminiThinking 2s ease-in-out infinite;
        }

        .thinking-spinner::before {
            content: '✦';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            font-size: 12px;
            animation: geminiStarRotate 3s linear infinite;
        }

        /* Search-specific styling */
        .searching-message {
            display: flex;
            gap: 16px;
            padding: 0;
            opacity: 0;
            animation: messageSlideIn 0.3s ease forwards;
        }

        .searching-avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--search-color), #ff6b35);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            margin-top: 4px;
        }

        .searching-spinner {
            width: 24px;
            height: 24px;
            background: linear-gradient(135deg, var(--search-color), #ff6b35);
            border-radius: 50%;
            position: relative;
            animation: searchingSpinner 1.5s ease-in-out infinite;
        }

        .searching-spinner::before {
            content: '🔍';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 12px;
            animation: searchingRotate 2s linear infinite;
        }

        .searching-text {
            display: flex;
            align-items: center;
            gap: 8px;
            padding-top: 4px;
            color: var(--search-color);
            font-weight: 500;
        }

        @keyframes searchingSpinner {
            0%, 100% { 
                transform: scale(1);
                opacity: 0.8;
                box-shadow: 0 0 20px rgba(255, 149, 0, 0.3);
            }
            50% { 
                transform: scale(1.1);
                opacity: 1;
                box-shadow: 0 0 30px rgba(255, 107, 53, 0.5);
            }
        }

        @keyframes searchingRotate {
            0% { transform: translate(-50%, -50%) rotate(0deg); }
            100% { transform: translate(-50%, -50%) rotate(360deg); }
        }

        @keyframes geminiThinking {
            0%, 100% { 
                transform: scale(1);
                opacity: 0.8;
                box-shadow: 0 0 20px rgba(26, 115, 232, 0.3);
            }
            50% { 
                transform: scale(1.1);
                opacity: 1;
                box-shadow: 0 0 30px rgba(52, 168, 83, 0.5);
            }
        }

        .thinking-dots {
            display: flex;
            align-items: center;
            gap: 4px;
            padding-top: 4px;
        }

        .thinking-dot {
            width: 6px;
            height: 6px;
            background: var(--text-secondary);
            border-radius: 50%;
            animation: thinkingPulse 1.4s ease-in-out infinite both;
        }

        .thinking-dot:nth-child(1) { animation-delay: -0.32s; }
        .thinking-dot:nth-child(2) { animation-delay: -0.16s; }
        .thinking-dot:nth-child(3) { animation-delay: 0; }

        @keyframes thinkingPulse {
            0%, 80%, 100% {
                transform: scale(0.8);
                opacity: 0.5;
            }
            40% {
                transform: scale(1);
                opacity: 1;
            }
        }

        .input-area {
            padding: 24px 0 32px;
            background: var(--surface-primary);
        }

        .input-container {
            position: relative;
            max-width: 768px;
            margin: 0 auto;
            background: var(--surface-tertiary);
            border-radius: 12px;
            border: 1px solid var(--border-light);
            overflow: hidden;
            transition: all 0.15s ease;
        }

        .input-container:focus-within {
            border-color: var(--text-secondary);
            box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.1);
        }

        .input-wrapper {
            display: flex;
            align-items: flex-end;
            min-height: 52px;
            position: relative;
        }

        .message-input {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-size: 16px;
            line-height: 1.5;
            padding: 14px 48px 14px 16px;
            resize: none;
            outline: none;
            max-height: 200px;
            min-height: 24px;
            overflow-y: auto;
            font-family: inherit;
        }

        .message-input::placeholder {
            color: var(--text-secondary);
        }

        .send-button {
            position: absolute;
            right: 12px;
            bottom: 12px;
            width: 28px;
            height: 28px;
            background: var(--text-primary);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            color: var(--surface-primary);
        }

        .send-button:hover {
            background: var(--text-secondary);
        }

        .send-button:disabled {
            background: var(--text-tertiary);
            cursor: not-allowed;
        }

        .stop-button {
            position: absolute;
            right: 12px;
            bottom: 12px;
            width: 28px;
            height: 28px;
            background: var(--danger);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            color: white;
            z-index: 1;
        }

        .stop-button:hover {
            background: #dc2626;
            transform: scale(1.05);
        }

        .stop-button:active {
            transform: scale(0.95);
        }

        @keyframes messageSlideIn {
            from {
                opacity: 0;
                transform: translateY(8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes geminiStarRotate {
            0% { transform: translate(-50%, -50%) rotate(0deg); }
            100% { transform: translate(-50%, -50%) rotate(360deg); }
        }

        pre {
            background: var(--surface-secondary) !important;
            border: 1px solid var(--border-light) !important;
            border-radius: 8px !important;
            padding: 16px !important;
            margin: 16px 0 !important;
            overflow-x: auto;
        }

        code {
            background: var(--surface-secondary) !important;
            color: var(--text-primary) !important;
            padding: 2px 6px !important;
            border-radius: 4px !important;
            font-size: 13px !important;
            font-family: 'SF Mono', Monaco, 'Inconsolata', 'Roboto Mono', monospace;
        }

        ::-webkit-scrollbar {
            width: 6px;
        }

        ::-webkit-scrollbar-track {
            background: var(--surface-secondary);
            border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border-light);
            border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-tertiary);
        }

        /* Firefox scrollbar */
        * {
            scrollbar-width: thin;
            scrollbar-color: var(--border-light) var(--surface-secondary);
        }

        @media (max-width: 768px) {
            .sidebar {
                position: fixed;
                left: -260px;
                top: 0;
                height: 100vh;
                z-index: 1000;
                transition: left 0.3s ease;
            }
            
            .sidebar.open {
                left: 0;
            }
            
            .main-content {
                margin-left: 0;
            }
            
            .chat-container {
                padding: 0 12px;
            }
            
            .chat-messages {
                max-height: calc(100vh - 160px);
            }
            
            .welcome-suggestions {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="app-layout">
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <button class="new-chat-btn" onclick="startNewChat()">
                    <i class="fas fa-plus"></i>
                    New Chat
                </button>
            </div>
            
            <div class="chat-history" id="chatHistory">
                <!-- Chat items will be populated here -->
            </div>
            
            <div class="sidebar-footer">
                <div class="user-info">
                    <div class="user-details">
                        <div class="user-avatar"></div>
                        <span>{{ user.username }}</span>
                    </div>
                    <a href="{{ url_for('settings') }}" class="settings-btn" title="Settings">
                        <i class="fas fa-cog"></i>
                    </a>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="model-selector">
                <select class="model-dropdown" id="modelSelect">
                    {% for model_id, model_name in available_models.items() %}
                    <option value="{{ model_id }}">{{ model_name }}</option>
                    {% endfor %}
                </select>
            </div>
            
            <div class="chat-container">
                <div class="chat-messages" id="chatMessages">
                    <div class="welcome-screen" id="welcomeScreen">
                        <div class="welcome-logo"></div>
                        <div>
                            <h1 class="welcome-title">Hello {{ user.username }}!</h1>
                            <p class="welcome-subtitle">How can I help you today?</p>
                        </div>
                        <div class="welcome-suggestions">
                            <div class="suggestion-card" onclick="sendSuggestion('Search for the latest tech news')">
                                <div class="suggestion-title">🔍 Search News</div>
                                <div class="suggestion-description">Find the latest technology news</div>
                            </div>
                            <div class="suggestion-card" onclick="sendSuggestion('What is artificial intelligence?')">
                                <div class="suggestion-title">🤖 AI Knowledge</div>
                                <div class="suggestion-description">Learn about AI concepts</div>
                            </div>
                            <div class="suggestion-card" onclick="sendSuggestion('Search for chocolate cake recipes')">
                                <div class="suggestion-title">🔍 Find Recipes</div>
                                <div class="suggestion-description">Search for delicious recipes</div>
                            </div>
                            <div class="suggestion-card" onclick="sendSuggestion('How does machine learning work?')">
                                <div class="suggestion-title">🧠 Tech Help</div>
                                <div class="suggestion-description">Get technical explanations</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="input-area">
                    <div class="input-container">
                        <div class="input-wrapper">
                            <textarea 
                                class="message-input" 
                                id="messageInput" 
                                placeholder="Send a message to Gemini..."
                                rows="1"
                                onkeydown="handleKeyDown(event)"
                                oninput="adjustTextareaHeight(this)"
                            ></textarea>
                            <button class="send-button" id="sendButton" onclick="sendMessage()" disabled>
                                <i class="fas fa-arrow-up"></i>
                            </button>
                            <button class="stop-button" id="stopButton" onclick="stopGeneration()" style="display: none;">
                                <i class="fas fa-stop"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <script>
        // Global variables
        let isGenerating = false;
        let currentGenerationController = null;

        // DOM elements
        const chatMessages = document.getElementById('chatMessages');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const stopButton = document.getElementById('stopButton');
        const welcomeScreen = document.getElementById('welcomeScreen');
        const modelSelect = document.getElementById('modelSelect');

        // Initialize app
        document.addEventListener('DOMContentLoaded', function() {
            messageInput.focus();
        });

        // Input handling
        messageInput.addEventListener('input', function() {
            sendButton.disabled = !this.value.trim();
        });

        function handleKeyDown(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                if (!isGenerating && messageInput.value.trim()) {
                    sendMessage();
                }
            }
        }

        function adjustTextareaHeight(element) {
            element.style.height = 'auto';
            element.style.height = Math.min(element.scrollHeight, 200) + 'px';
        }

        function sendSuggestion(text) {
            messageInput.value = text;
            sendMessage();
        }

        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message || isGenerating) return;
            
            // Hide welcome screen
            if (welcomeScreen) {
                welcomeScreen.style.display = 'none';
            }
            
            // Add user message
            addMessage('user', message);
            
            // Clear input
            messageInput.value = '';
            sendButton.disabled = true;
            adjustTextareaHeight(messageInput);
            
            // Update UI state
            isGenerating = true;
            sendButton.style.display = 'none';
            stopButton.style.display = 'flex';
            
            // Check if this looks like a search query
            const searchKeywords = ['search', 'find', 'look up', 'latest', 'recent', 'current', 'today', 'news', 'weather', 'חפש', 'מצא', 'חדשות'];
            const needsSearch = searchKeywords.some(keyword => message.toLowerCase().includes(keyword));
            
            let statusElement;
            if (needsSearch) {
                // Show searching animation
                statusElement = addSearchingMessage();
            } else {
                // Show thinking animation
                statusElement = addThinkingMessage();
            }
            
            try {
                // Create abort controller for stopping generation
                currentGenerationController = new AbortController();
                
                // Send request
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        model: modelSelect.value
                    }),
                    signal: currentGenerationController.signal
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                // Remove status animation
                removeMessage(statusElement);
                
                if (data.response) {
                    // Add assistant response with typing effect
                    await addMessage('assistant', data.response, true);
                } else {
                    addMessage('assistant', 'Sorry, an error occurred: ' + (data.error || 'Unknown error'));
                }
                
            } catch (error) {
                removeMessage(statusElement);
                if (error.name !== 'AbortError') {
                    addMessage('assistant', 'Sorry, a connection error occurred. Please try again.');
                    console.error('Error:', error);
                } else {
                    console.log('Generation stopped by user');
                }
            } finally {
                // Reset UI state only if not already reset by stop button
                if (isGenerating) {
                    isGenerating = false;
                    sendButton.style.display = 'flex';
                    stopButton.style.display = 'none';
                    currentGenerationController = null;
                    messageInput.focus();
                }
            }
        }

        function stopGeneration() {
            if (currentGenerationController) {
                currentGenerationController.abort();
            }
            
            // Immediately stop any ongoing typing effect
            isGenerating = false;
            
            // Reset UI state immediately
            sendButton.style.display = 'flex';
            stopButton.style.display = 'none';
            
            // Re-enable input
            messageInput.focus();
            
            // Remove any thinking/searching animations
            const thinkingElements = document.querySelectorAll('.thinking-message, .searching-message');
            thinkingElements.forEach(element => {
                if (element.parentNode) {
                    element.parentNode.removeChild(element);
                }
            });
            
            // Add a stopped message
            addMessage('assistant', '⏹️ Generation stopped by user.');
        }

        function addMessage(role, content, useTypingEffect = false) {
            const messageGroup = document.createElement('div');
            messageGroup.className = 'message-group';
            
            const message = document.createElement('div');
            message.className = `message ${role}`;
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            
            const messageContent = document.createElement('div');
            messageContent.className = 'message-content';
            
            const messageText = document.createElement('div');
            messageText.className = 'message-text';
            
            if (role === 'assistant' && useTypingEffect) {
                return typeMessageWithEffect(messageText, content, message, avatar, messageContent, messageGroup);
            } else {
                if (role === 'assistant') {
                    messageText.innerHTML = marked.parse(content);
                    hljs.highlightAll();
                } else {
                    messageText.textContent = content;
                }
            }
            
            messageContent.appendChild(messageText);
            
            // Add message actions for assistant messages
            if (role === 'assistant') {
                const actions = document.createElement('div');
                actions.className = 'message-actions';
                
                const copyBtn = document.createElement('button');
                copyBtn.className = 'message-action-btn';
                copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
                copyBtn.onclick = () => copyToClipboard(content);
                
                actions.appendChild(copyBtn);
                messageContent.appendChild(actions);
            }
            
            message.appendChild(avatar);
            message.appendChild(messageContent);
            messageGroup.appendChild(message);
            
            chatMessages.appendChild(messageGroup);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // Animation
            requestAnimationFrame(() => {
                messageGroup.style.opacity = '0';
                messageGroup.style.transform = 'translateY(8px)';
                messageGroup.style.transition = 'all 0.3s ease';
                
                requestAnimationFrame(() => {
                    messageGroup.style.opacity = '1';
                    messageGroup.style.transform = 'translateY(0)';
                });
            });
            
            return messageGroup;
        }

        async function typeMessageWithEffect(messageText, content, message, avatar, messageContent, messageGroup) {
            return new Promise((resolve) => {
                messageContent.appendChild(messageText);
                
                // Add message actions
                const actions = document.createElement('div');
                actions.className = 'message-actions';
                
                const copyBtn = document.createElement('button');
                copyBtn.className = 'message-action-btn';
                copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
                copyBtn.onclick = () => copyToClipboard(content);
                
                actions.appendChild(copyBtn);
                messageContent.appendChild(actions);
                
                message.appendChild(avatar);
                message.appendChild(messageContent);
                messageGroup.appendChild(message);
                
                chatMessages.appendChild(messageGroup);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                
                // Animation
                requestAnimationFrame(() => {
                    messageGroup.style.opacity = '0';
                    messageGroup.style.transform = 'translateY(8px)';
                    messageGroup.style.transition = 'all 0.3s ease';
                    
                    requestAnimationFrame(() => {
                        messageGroup.style.opacity = '1';
                        messageGroup.style.transform = 'translateY(0)';
                    });
                });
                
                // Typing effect
                let i = 0;
                const typingSpeed = 8;
                
                function typeCharacter() {
                    if (i < content.length && isGenerating) {
                        const currentText = content.substring(0, i + 1);
                        messageText.innerHTML = marked.parse(currentText);
                        hljs.highlightAll();
                        i++;
                        
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                        setTimeout(typeCharacter, typingSpeed + Math.random() * 5);
                    } else {
                        // Only complete the message if generation wasn't stopped
                        if (isGenerating) {
                            messageText.innerHTML = marked.parse(content);
                            hljs.highlightAll();
                        }
                        resolve(messageGroup);
                    }
                }
                
                typeCharacter();
            });
        }

        function addSearchingMessage() {
            const searchingGroup = document.createElement('div');
            searchingGroup.className = 'message-group';
            
            const searching = document.createElement('div');
            searching.className = 'searching-message';
            
            const avatar = document.createElement('div');
            avatar.className = 'searching-avatar';
            
            const spinner = document.createElement('div');
            spinner.className = 'searching-spinner';
            avatar.appendChild(spinner);
            
            const searchText = document.createElement('div');
            searchText.className = 'searching-text';
            searchText.textContent = 'Searching...';
            
            searching.appendChild(avatar);
            searching.appendChild(searchText);
            searchingGroup.appendChild(searching);
            
            chatMessages.appendChild(searchingGroup);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            return searchingGroup;
        }

        function addThinkingMessage() {
            const thinkingGroup = document.createElement('div');
            thinkingGroup.className = 'message-group';
            
            const thinking = document.createElement('div');
            thinking.className = 'thinking-message';
            
            const avatar = document.createElement('div');
            avatar.className = 'thinking-avatar';
            
            const spinner = document.createElement('div');
            spinner.className = 'thinking-spinner';
            avatar.appendChild(spinner);
            
            const dots = document.createElement('div');
            dots.className = 'thinking-dots';
            
            for (let i = 0; i < 3; i++) {
                const dot = document.createElement('div');
                dot.className = 'thinking-dot';
                dots.appendChild(dot);
            }
            
            thinking.appendChild(avatar);
            thinking.appendChild(dots);
            thinkingGroup.appendChild(thinking);
            
            chatMessages.appendChild(thinkingGroup);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            return thinkingGroup;
        }

        function removeMessage(element) {
            if (element && element.parentNode) {
                element.parentNode.removeChild(element);
            }
        }

        function startNewChat() {
            chatMessages.innerHTML = '';
            
            // Show welcome screen
            const welcomeHtml = `
                <div class="welcome-screen" id="welcomeScreen">
                    <div class="welcome-logo"></div>
                    <div>
                        <h1 class="welcome-title">Hello!</h1>
                        <p class="welcome-subtitle">How can I help you today?</p>
                    </div>
                    <div class="welcome-suggestions">
                        <div class="suggestion-card" onclick="sendSuggestion('Search for the latest tech news')">
                            <div class="suggestion-title">🔍 Search News</div>
                            <div class="suggestion-description">Find the latest technology news</div>
                        </div>
                        <div class="suggestion-card" onclick="sendSuggestion('What is artificial intelligence?')">
                            <div class="suggestion-title">🤖 AI Knowledge</div>
                            <div class="suggestion-description">Learn about AI concepts</div>
                        </div>
                        <div class="suggestion-card" onclick="sendSuggestion('Search for chocolate cake recipes')">
                            <div class="suggestion-title">🔍 Find Recipes</div>
                            <div class="suggestion-description">Search for delicious recipes</div>
                        </div>
                        <div class="suggestion-card" onclick="sendSuggestion('How does machine learning work?')">
                            <div class="suggestion-title">🧠 Tech Help</div>
                            <div class="suggestion-description">Get technical explanations</div>
                        </div>
                    </div>
                </div>
            `;
            
            chatMessages.innerHTML = welcomeHtml;
            messageInput.focus();
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                // Toast notification can be added here
            });
        }
    </script>
</body>
</html>
"""

# Routes
@app.route("/")
@login_required
def index():
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return render_template_string(MAIN_TEMPLATE, available_models=AVAILABLE_MODELS, user=user)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please fill in all fields', 'error')
            return render_template_string(LOGIN_TEMPLATE)
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if user and verify_password(password, user['password_hash']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            # Update last login
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            conn.close()
            
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
        
        conn.close()
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route("/register", methods=["POST"])
def register():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # Validation
    if not all([username, email, password, confirm_password]):
        flash('Please fill in all fields', 'error')
        return render_template_string(LOGIN_TEMPLATE)
    
    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return render_template_string(LOGIN_TEMPLATE)
    
    if len(password) < 6:
        flash('Password must be at least 6 characters long', 'error')
        return render_template_string(LOGIN_TEMPLATE)
    
    conn = get_db_connection()
    
    # Check if user already exists
    existing_user = conn.execute('SELECT id FROM users WHERE email = ? OR username = ?', (email, username)).fetchone()
    if existing_user:
        flash('User with this email or username already exists', 'error')
        conn.close()
        return render_template_string(LOGIN_TEMPLATE)
    
    # Create new user
    password_hash = hash_password(password)
    
    try:
        cursor = conn.execute('''
            INSERT INTO users (username, email, password_hash) 
            VALUES (?, ?, ?)
        ''', (username, email, password_hash))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Auto login
        session['user_id'] = user_id
        session['username'] = username
        
        flash('Registered successfully!', 'success')
        conn.close()
        return redirect(url_for('index'))
        
    except Exception as e:
        flash('Error creating account', 'error')
        conn.close()
        return render_template_string(LOGIN_TEMPLATE)

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    conn = get_db_connection()
    
    if request.method == "POST":
        google_api_key = request.form.get('google_api_key', '').strip()
        serpapi_key = request.form.get('serpapi_key', '').strip()
        
        conn.execute('''
            UPDATE users 
            SET google_api_key = ?, serpapi_key = ? 
            WHERE id = ?
        ''', (google_api_key or None, serpapi_key or None, session['user_id']))
        
        conn.commit()
        flash('Settings saved successfully!', 'success')
    
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return render_template_string(SETTINGS_TEMPLATE, user=user)

@app.route("/logout")
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    try:
        data = request.json
        message = data.get('message', '').strip()
        model = data.get('model', 'gemini-1.5-flash')
        
        if not message:
            return jsonify({"error": "No question received"}), 400
        
        # Get user's API keys
        api_keys = get_user_api_keys(session['user_id'])
        
        if not api_keys['google_api_key']:
            return jsonify({
                "error": "Please set up Google API key in settings to use Gemini"
            }), 400
        
        # Check if we should search the internet
        needs_search = should_search_internet(message)
        search_results = ""
        searched_internet = False
        
        if needs_search and api_keys['serpapi_key']:
            search_results = serpapi_search(message, api_keys['serpapi_key'])
            searched_internet = True
        elif needs_search and not api_keys['serpapi_key']:
            search_results = "Web search unavailable - please set SerpAPI key in settings"
        
        # Generate AI response
        bot_response = generate_ai_response(message, search_results, model, api_keys['google_api_key'], searched_internet)
        
        # Convert to HTML markdown
        bot_response_html = markdown.markdown(
            bot_response, 
            extensions=['fenced_code', 'tables', 'toc']
        )
        
        return jsonify({
            "response": bot_response_html,
            "timestamp": datetime.now().strftime("%H:%M"),
            "model_used": model,
            "searched_internet": searched_internet
        })
        
    except Exception as e:
        app.logger.error(f"Chat error: {str(e)}")
        return jsonify({
            "error": "An error occurred while processing the question. Please check your API keys in settings and try again."
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Page not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Initialize database on startup
if __name__ == "__main__":
    init_db()
    
    print("🚀 Starting Gemini AI with Authentication...")
    print("🔐 Features:")
    print("   - User registration and login")
    print("   - Secure API key storage in database")
    print("   - Beautiful Gemini UI with animations")
    print("   - Multiple Gemini models (1.5-flash, 2.0-flash, 2.5-flash, 2.5-pro)")
    print("   - Smart web search integration (only when needed)")
    print("   - Real-time typing effects")
    print("   - Secure session management")
    print("   - Improved user chat bubbles with proper user icon")
    print("   - Intelligent search detection with 'Searching...' animation")
    print("📝 Setup Instructions:")
    print("   1. Run the application")
    print("   2. Register a new account or login")
    print("   3. Go to Settings and add your API keys:")
    print("      - Google Gemini API Key (required)")
    print("      - SerpAPI Key (optional, for web search)")
    print("📡 Server starting on http://localhost:5000")
    
    app.run(
        host="0.0.0.0", 
        port=5000, 
        debug=True,
        threaded=True
    )