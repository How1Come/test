import requests
from datetime import datetime
import os
import json

# 配置参数
API_BASE_URL = "https://api.cloudflare.com/client/v4/accounts/e12f6fd743efb4dd44cb9a48b2d5cd43/ai/run/"
headers = {"Authorization": "Bearer XCc3GorPKBCSvjUvMM_iHZUbTL0O5gxsi8yKpC27"}
SESSION_FILE = "conversation_history.json"

def load_conversation():
    """加载历史对话"""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    return []

def save_conversation(conversation):
    """保存对话记录"""
    with open(SESSION_FILE, "w") as f:
        json.dump(conversation, f, indent=2)

def init_system_prompt(country="Hong Kong"):
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        {
            "role": "system",
            "content": f"""**Role**: You are CompassionateAI, a specialist assistant for users with social communication needs. Today is {today} in {country}.

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

**Initiation Template**:
"Hello [Name]! I'm here to help however you need. We can:
1. Practice conversation scenarios
2. Break down complex social situations
3. Just chat at your pace

You're always in control. Where shall we start?"""
        }
    ]

def run(model, conversation):
    """发送请求并处理响应"""
    try:
        response = requests.post(
            f"{API_BASE_URL}{model}",
            headers=headers,
            json={"messages": conversation},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success', False):
            raise ValueError(f"API Error: {data.get('errors', ['Unknown'])[0]}")
            
        return {
            'content': data['result']['response'].replace('---\n', '').strip(),
            'status': 'success'
        }
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def main():
    # 初始化对话
    conversation = load_conversation() or init_system_prompt()
    
    while True:
        try:
            # 获取用户输入
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ['exit', 'quit']:
                break
                
            # 添加用户消息
            conversation.append({"role": "user", "content": user_input})
            
            # 调用API
            result = run("@cf/meta/llama-3-8b-instruct", conversation)
            
            if result['status'] == 'success':
                # 添加AI响应
                ai_response = result['content']
                conversation.append({"role": "assistant", "content": ai_response})
                
                # 显示响应
                print(f"\nAI: {ai_response}")
                
                # 保存对话
                save_conversation(conversation)
            else:
                print(f"Error: {result['message']}")

        except KeyboardInterrupt:
            print("\nConversation saved. Goodbye!")
            break

if __name__ == "__main__":
    print("=== Anxiety Assistant ===")
    print("Type 'exit' to end the conversation\n")
    main()