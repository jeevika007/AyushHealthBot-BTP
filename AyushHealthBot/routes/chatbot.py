from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from models import db, ChatMessage, User, Question
import json
import uuid
import requests
from datetime import datetime
import openai  # You'll need to pip install openai

chatbot = Blueprint('chatbot', __name__)

# Set your OpenAI API key
# openai.api_key = "YOUR_OPENAI_API_KEY"  # Uncomment and add your API key

@chatbot.route('/chat')
@login_required
def chat_interface():
    """Render the chat interface"""
    conversation_id = request.args.get('conversation_id')
    
    # Create new conversation if none exists
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    
    # Get chat history for this conversation
    chat_history = ChatMessage.query.filter_by(
        conversation_id=conversation_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return render_template('chat.html', 
                          conversation_id=conversation_id,
                          chat_history=chat_history)

@chatbot.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    """API endpoint for chat interactions"""
    data = request.json
    user_message = data.get('message')
    conversation_id = data.get('conversation_id', str(uuid.uuid4()))
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Save user message to database
    user_chat = ChatMessage(
        content=user_message,
        is_bot=False,
        conversation_id=conversation_id,
        user_id=current_user.id
    )
    db.session.add(user_chat)
    db.session.commit()
    
    # Get conversation history
    chat_history = ChatMessage.query.filter_by(
        conversation_id=conversation_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    # Format conversation history for AI context
    conversation_text = ""
    for msg in chat_history:
        prefix = "Bot: " if msg.is_bot else f"{current_user.username}: "
        conversation_text += prefix + msg.content + "\n"
    
    # Get user context data
    user_context = {
        'user_id': current_user.id,
        'username': current_user.username,
        'role': current_user.role,
        'recent_questions': []
    }
    
    # Add recent questions to context if user is a patient
    if current_user.role == 'patient':
        recent_questions = Question.query.filter_by(
            patient_id=current_user.id
        ).order_by(Question.created_at.desc()).limit(3).all()
        
        user_context['recent_questions'] = [
            {'title': q.title, 'answered': q.answered, 'specialization': q.specialization}
            for q in recent_questions
        ]
    
    # Create system message with context
    system_message = f"""
    You are a health assistant for AyushHealthBot. The current user is {current_user.username} who is a {current_user.role}.
    
    Your task is to provide helpful, accurate health information while being mindful of these guidelines:
    1. You are not a replacement for professional medical advice
    2. For serious symptoms, always advise seeing a doctor
    3. Keep responses concise and easily understandable
    4. Be supportive and empathetic
    
    Based on the conversation history, provide a contextually aware response.
    """
    
    try:
        # Uncomment this section when you have your OpenAI API key
        """
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": conversation_text + "\nPlease respond to my last message."}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        bot_response = response.choices[0].message.content.strip()
        """
        
        # For demo, use a mock response
        bot_response = generate_mock_response(user_message, user_context)
        
        # Save bot response to database
        bot_chat = ChatMessage(
            content=bot_response,
            is_bot=True,
            conversation_id=conversation_id,
            context_data=json.dumps(user_context)
        )
        db.session.add(bot_chat)
        db.session.commit()
        
        return jsonify({
            'response': bot_response,
            'conversation_id': conversation_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_mock_response(user_message, context):
    """Generate mock responses for demo purposes"""
    user_message = user_message.lower()
    role = context.get('role', '')
    
    if 'hello' in user_message or 'hi' in user_message:
        return f"Hello! How can I help you with your health today?"
    
    if 'headache' in user_message:
        return "I see you're experiencing headaches. This could be due to stress, dehydration, or eye strain. Make sure you're drinking enough water and taking breaks from screens. If it persists, please consult a doctor."
    
    if 'appointment' in user_message:
        if role == 'patient':
            return "I can help you book an appointment. You can do this directly from your dashboard by clicking on 'Consult Doctor' and then selecting the 'Book Appointment' tab."
        else:
            return "You can manage all your patient appointments from your doctor dashboard."
    
    if 'symptoms' in user_message:
        return "To check your symptoms, please use the 'Test/Examine' feature on your dashboard where our AI can analyze your symptoms and provide possible conditions."
    
    if 'thank' in user_message:
        return "You're welcome! Is there anything else I can help you with?"
    
    # Default response
    return "I'm here to help with your health questions. Could you provide more details about your concern?" 