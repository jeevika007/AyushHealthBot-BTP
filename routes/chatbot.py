from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from models import db, ChatMessage, Conversation, User
import json
import uuid
from datetime import datetime
import sys
import os

# Import custom chatbot processor
from chatbot_processor import ChatbotProcessor

chatbot = Blueprint('chatbot', __name__)

# Initialize chatbot processor
processor = ChatbotProcessor()

@chatbot.route('/chat')
@login_required
def chat_interface():
    """Render the chat interface"""
    # Get active conversation ID or create a new one
    conversation_id = request.args.get('conversation_id')
    conversation = None
    
    if conversation_id:
        # Look up existing conversation
        conversation = Conversation.query.filter_by(
            conversation_id=conversation_id,
            user_id=current_user.id
        ).first()
    
    if not conversation:
        # Create new conversation
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
            language='en',  # Default language
            context_data=json.dumps({
                'symptoms': [],
                'topics': [],
                'last_updated': datetime.now().isoformat()
            })
        )
        db.session.add(conversation)
        db.session.commit()
    
    # Get chat history for this conversation
    chat_history = ChatMessage.query.filter_by(
        conversation_id=conversation_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return render_template('chat.html', 
                         conversation_id=conversation_id,
                         chat_history=chat_history)

@chatbot.route('/send', methods=['POST'])
@login_required
def send_message():
    """API endpoint to send a message to the chatbot"""
    data = request.json
    user_message = data.get('message')
    conversation_id = data.get('conversation_id')
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    if not conversation_id:
        # Create new conversation if none exists
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
            language='en',  # Default language
            context_data=json.dumps({
                'symptoms': [],
                'topics': [],
                'last_updated': datetime.now().isoformat()
            })
        )
        db.session.add(conversation)
        db.session.commit()
    else:
        # Get existing conversation
        conversation = Conversation.query.filter_by(
            conversation_id=conversation_id,
            user_id=current_user.id
        ).first()
        
        if not conversation:
            # Create if it doesn't exist (should not happen normally)
            conversation = Conversation(
                conversation_id=conversation_id,
                user_id=current_user.id,
                language='en',
                context_data=json.dumps({
                    'symptoms': [],
                    'topics': [],
                    'last_updated': datetime.now().isoformat()
                })
            )
            db.session.add(conversation)
            db.session.commit()
    
    # Detect language and update conversation language if needed
    detected_language = processor.detect_language(user_message)
    if detected_language != conversation.language:
        conversation.language = detected_language
    
    # Extract intent and entities from user message
    intent = processor.detect_intent(user_message, detected_language)
    entities = processor.extract_entities(user_message, detected_language)
    
    # Convert entities to JSON for storage
    entities_json = json.dumps(entities) if entities else None
    
    # Save user message to database
    user_chat = ChatMessage(
        conversation_id=conversation_id,
        content=user_message,
        is_bot=False,
        user_id=current_user.id,
        language=detected_language,
        intent=intent,
        entities=entities_json
    )
    db.session.add(user_chat)
    db.session.commit()
    
    # Get conversation history
    chat_history = ChatMessage.query.filter_by(
        conversation_id=conversation_id
    ).order_by(ChatMessage.created_at.asc()).limit(10).all()
    
    # Get current context and update it with information from this message
    current_context = conversation.get_context()
    updated_context = processor.update_context_from_message(user_message, current_context)
    
    # Update conversation context
    conversation.context_data = json.dumps(updated_context)
    db.session.commit()
    
    try:
        # Generate bot response
        bot_response = processor.generate_response(
            user_message, 
            chat_history, 
            updated_context
        )
        
        # Save bot response to database
        bot_chat = ChatMessage(
            conversation_id=conversation_id,
            content=bot_response,
            is_bot=True,
            user_id=current_user.id,
            language=detected_language
        )
        db.session.add(bot_chat)
        db.session.commit()
        
        # Return response to client
        return jsonify({
            'message': bot_response,
            'conversation_id': conversation_id,
            'entities_detected': entities,
            'language': detected_language
        })
        
    except Exception as e:
        print(f"Error generating response: {str(e)}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500

@chatbot.route('/history/<conversation_id>')
@login_required
def get_history(conversation_id):
    """Get chat history for a specific conversation"""
    # Verify the conversation belongs to the current user
    conversation = Conversation.query.filter_by(
        conversation_id=conversation_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get chat messages
    messages = ChatMessage.query.filter_by(
        conversation_id=conversation_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return jsonify({
        'conversation_id': conversation_id,
        'language': conversation.language,
        'messages': [msg.to_dict() for msg in messages],
        'context': conversation.get_context()
    })

@chatbot.route('/conversations')
@login_required
def list_conversations():
    """List all conversations for the current user"""
    conversations = Conversation.query.filter_by(
        user_id=current_user.id
    ).order_by(Conversation.last_updated.desc()).all()
    
    return jsonify({
        'conversations': [conv.to_dict() for conv in conversations]
    })

@chatbot.route('/new_conversation', methods=['POST'])
@login_required
def new_conversation():
    """Create a new conversation"""
    conversation_id = str(uuid.uuid4())
    conversation = Conversation(
        conversation_id=conversation_id,
        user_id=current_user.id,
        language=request.json.get('language', 'en'),
        context_data=json.dumps({
            'symptoms': [],
            'topics': [],
            'last_updated': datetime.now().isoformat()
        })
    )
    db.session.add(conversation)
    db.session.commit()
    
    return jsonify({
        'conversation_id': conversation_id,
        'message': 'New conversation created successfully'
    }) 