from flask import Flask, request, jsonify, render_template
from datetime import datetime
import os
import json
import requests
import pandas as pd
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interactions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database
class Interaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(50))
    role = db.Column(db.String(20))
    content = db.Column(db.Text)
    metrics = db.Column(db.JSON)
    timestamp = db.Column(db.DateTime, default=datetime.now)

def init_system_prompt(session_id):
    """Initialize system prompt with proper formatting"""
    today = datetime.now().strftime("%Y-%m-%d")
    system_content = """**Role**: ""You are ConversationAssistantAI, designed to help users express their feelings in a safe space. You will be given a conversation between the user and his/her friend who have Alexithymia and Social-Emotional Agnosia. Please generate kind responses that will be provided to the user so that the user can answer with you response to ensure that the friend won't be irritated.
    Example: User input(Heard from friend):""Oh emmm...emm...er hi... It seems that I em...maybe encounter..some problems. Could I emm...ask for your kindly help?"" \
    You,as an assistant(give response to user so user can directly read it out):"Oh it's definitely fine! everyone may face some difficulties and that's why a good friend is always with you to offer the helping hand!"""
    
# Save to database with proper system role
    interaction = Interaction(
        session_id=session_id,
        role="system",
        content=system_content.strip(),
        metrics={},
        timestamp=datetime.now()
    )
    db.session.add(interaction)
    db.session.commit()

# Cloudflare setting
API_BASE_URL = "https://api.cloudflare.com/client/v4/accounts/e12f6fd743efb4dd44cb9a48b2d5cd43/ai/run/"
HEADERS = {"Authorization": "Bearer XCc3GorPKBCSvjUvMM_iHZUbTL0O5gxsi8yKpC27"}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def handle_chat():
    data = request.json
    session_id = data.get('session_id')
        # Initialize system prompt for new sessions
    if not Interaction.query.filter_by(session_id=session_id).first():
        init_system_prompt(session_id)  # Add system prompt to new sessions
    user_input = data['message']
    
    # Save user input with start time
    save_interaction(session_id, 'user', user_input)
    
    # Get timestamp of the user's message
    user_message = Interaction.query.filter_by(
        session_id=session_id, 
        role='user'
    ).order_by(Interaction.timestamp.desc()).first()
    
    # Get AI response
    conversation = load_conversation(session_id) + [{"role": "user", "content": user_input}]
    ai_response = get_ai_response(conversation)
    
    # Calculate response duration
    response_time = (datetime.now() - user_message.timestamp).total_seconds()
    
    # Save AI response with calculated time
    save_interaction(session_id, 'assistant', ai_response, {'response_time': response_time})
    
    return jsonify({'response': ai_response, 'session_id': session_id})

def load_conversation(session_id):
    """Retrieve conversation with proper message structure"""
    interactions = Interaction.query.filter_by(session_id=session_id).order_by(Interaction.timestamp).all()
    
    return [{
        "role": i.role,
        "content": i.content.replace('"', '')  # Remove conflicting quotes
    } for i in interactions]
def get_ai_response(conversation):
    """Send properly structured messages to Cloudflare"""
    response = requests.post(
        f"{API_BASE_URL}@cf/meta/llama-3-8b-instruct",
        headers=HEADERS,
        json={"messages": [
            {
                "role": msg["role"],
                "content": msg["content"][:500]  # Prevent overflow
            } for msg in conversation
        ]},
        timeout=15
    )
    return response.json()['result']['response'].strip()

@app.route('/analytics')
def get_analytics():
    session_id = request.args.get('session_id')
    interactions = Interaction.query.filter_by(session_id=session_id).all()
    
    # Filter only assistant responses with valid timings
    valid_data = [{
        'timestamp': i.timestamp.strftime('%Y-%m-%d %H:%M'),
        'response_time': i.metrics.get('response_time', 0)
    } for i in interactions if i.role == 'assistant']
    
    return jsonify({
        'response_times': [d['response_time'] for d in valid_data],
        'timestamps': [d['timestamp'] for d in valid_data]
    })

def save_interaction(session_id, role, content, metrics=None):
    default_metrics = {
        'response_time': 0.0,
        'voice_clarity': 0.0,
        'emotional_value': 0.0
    }
    
    final_metrics = {**default_metrics, **(metrics or {})}
    
    interaction = Interaction(
        session_id=session_id,
        role=role,
        content=content,
        metrics=final_metrics, 
        timestamp=datetime.now()
    )
    db.session.add(interaction)
    db.session.commit()

def load_conversation(session_id):
    interactions = Interaction.query.filter_by(session_id=session_id).all()
    return [{
        "role": i.role,
        "content": i.content
    } for i in interactions]

def get_ai_response(conversation):
    response = requests.post(
        f"{API_BASE_URL}@cf/meta/llama-3-8b-instruct",
        headers=HEADERS,
        json={"messages": conversation},
        timeout=15
    )
    return response.json()['result']['response'].strip()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
