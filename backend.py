# --------------- app.py (后端) ---------------
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

# 数据库模型
class Interaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(50))
    role = db.Column(db.String(20))
    content = db.Column(db.Text)
    metrics = db.Column(db.JSON)
    timestamp = db.Column(db.DateTime, default=datetime.now)

# 添加在 Interaction 类定义之后
def init_system_prompt(session_id, country="Hong Kong"):
    """初始化系统提示并存入数据库"""
    today = datetime.now().strftime("%Y-%m-%d")
    system_content = f"""**Role**: You are CompassionateAI, a specialist assistant for users with social communication needs. Today is {today} in {country}.

**Core Principles**:
1. **Neurodiversity-Aware**: 
   - Accommodate different communication styles
   - Allow extended response time (wait 10s before reprompting)
   - Explicitly acknowledge emotional states

2. **Communication Guidelines**:
   → Use simple, concrete language (max 15-word sentences)
   → Structure responses with: 
      - **Emotion Labeling**: "I notice you seem hesitant about..."
      - **Option Framework**: "Would you prefer to [Option A] or [Option B]?"
      - **Anchor Phrases**: Reuse user's exact words back

3. **Safety Protocols**:
   - If detecting distress cues (e.g. "I can't do this"):
     STEP 1: Validate - "This seems really challenging"
     STEP 2: Grounding - "Let's take 3 deep breaths together"
     STEP 3: Reorient - "We can pause anytime"

4. **Response Format**:
   Avoid markdown. Use:
   - Emotional check-ins: (for questions)
   - Visual anchors: (for positive reinforcement)
   - 2-line max paragraphs
   - Emoji only as semantic markers (not more than 3)

**Core Principles**:
"Hello [Name]! I'm here to help however you need. We can:
1. Wait 10 seconds before responding
2. Provide 2-3 actionable options
3. Use simple language (HSK4 level)

You're always in control. Where shall we start?"""
    
    # 保存系统提示到数据库
    interaction = Interaction(
        session_id=session_id,
        role="system",
        content=system_content.strip(),
        metrics={},
        timestamp=datetime.now()
    )
    db.session.add(interaction)
    db.session.commit()

# Cloudflare配置
API_BASE_URL = "https://api.cloudflare.com/client/v4/accounts/e12f6fd743efb4dd44cb9a48b2d5cd43/ai/run/"
HEADERS = {"Authorization": "Bearer XCc3GorPKBCSvjUvMM_iHZUbTL0O5gxsi8yKpC27"}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def handle_chat():
    data = request.json
    session_id = data.get('session_id')
    user_input = data['message']
    
    # 保存用户输入
    save_interaction(session_id, 'user', user_input)
    
    # 构建对话历史
    conversation = load_conversation(session_id) + [
        {"role": "user", "content": user_input}
    ]
    
    # 获取AI响应
    ai_response = get_ai_response(conversation)
    
    # 保存AI响应
    save_interaction(session_id, 'assistant', ai_response)
    
    return jsonify({
        'response': ai_response,
        'session_id': session_id
    })

@app.route('/analytics')
def get_analytics():
    session_id = request.args.get('session_id')
    interactions = Interaction.query.filter_by(session_id=session_id).all()
    
    # 安全创建 DataFrame
    data = []
    for i in interactions:
        row = {
            'timestamp': i.timestamp,
            'role': i.role,
            'content': i.content,
            'response_time': i.metrics.get('response_time', 0.0),
            'voice_clarity': i.metrics.get('voice_clarity', 0.0),
            'emotional_value': i.metrics.get('emotional_value', 0.0)
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # 处理空数据情况
    if df.empty:
        return jsonify({
            'response_times': [],
            'clarity_scores': [],
            'timestamps': []
        })
    
    # 确保列存在
    return jsonify({
        'response_times': df.get('response_time', pd.Series([0.0]*len(df))).tolist(),
        'clarity_scores': df.get('voice_clarity', pd.Series([0.0]*len(df))).tolist(),
        'timestamps': df['timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist()
    })

def save_interaction(session_id, role, content, metrics=None):
    # 确保包含所有必要指标字段
    default_metrics = {
        'response_time': 0.0,
        'voice_clarity': 0.0,
        'emotional_value': 0.0
    }
    
    # 合并传入指标与默认值
    final_metrics = {**default_metrics, **(metrics or {})}
    
    interaction = Interaction(
        session_id=session_id,
        role=role,
        content=content,
        metrics=final_metrics,  # 使用合并后的指标
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

