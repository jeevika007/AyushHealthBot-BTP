import json
import re
import nltk
import spacy
from langdetect import detect
from textblob import TextBlob
import openai
import random
from datetime import datetime

# Download necessary NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# Try to load spaCy models
try:
    nlp_en = spacy.load("en_core_web_sm")
except:
    # If model is not available, use a simple tokenizer
    nlp_en = None

# Load OpenAI API key
try:
    with open('openai_api_key.txt', 'r') as f:
        openai.api_key = f.read().strip()
except:
    print("WARNING: OpenAI API key not found or invalid")

# Common symptom patterns and medical terms for detection
SYMPTOMS = [
    'fever', 'cough', 'cold', 'headache', 'pain', 'ache', 'sore throat', 'nausea',
    'vomiting', 'diarrhea', 'fatigue', 'weakness', 'dizziness', 'swelling',
    'rash', 'itching', 'bleeding', 'bruising', 'numbness', 'tingling',
    'bukhaar', 'khansi', 'sardi', 'sirdard', 'dard', 'galaa kharaab', 'chakkar',
    'kamzori', 'thakaan', 'ulti', 'dast', 'khujli', 'sujan'
]

# Intent classification patterns
INTENT_PATTERNS = {
    'greeting': [
        r'hello', r'hi', r'hey', r'howdy', r'greetings', r'good morning', r'good evening',
        r'namaste', r'namaskar', r'hello', r'hi', r'hey', r'howdy', r'greetings', r'good morning', r'good evening'
    ],
    'goodbye': [
        r'bye', r'goodbye', r'see you', r'see you later', r'farewell', r'take care',
        r'alvida', r'phir milenge', r'khuda hafiz'
    ],
    'symptom_report': [
        r'(have|having|got|getting|feeling|suffering from).*?('+"|".join(SYMPTOMS)+')',
        r'(मुझे|मैं).*?('+"|".join([s for s in SYMPTOMS if len(s) > 3])+')',
        r'('+"|".join(SYMPTOMS)+').*?(ho raha|ho rahi|hai)'
    ],
    'medicine_inquiry': [
        r'(medicine|medication|drug|treatment|cure|remedy)',
        r'(दवा|औषधि|इलाज|उपचार)'
    ],
    'appointment_inquiry': [
        r'(appointment|book|schedule|meet|consult|doctor)',
        r'(अपॉइंटमेंट|मुलाकात|डॉक्टर)'
    ],
    'thank': [
        r'(thank|thanks|thank you|thanks a lot|appreciate)',
        r'(धन्यवाद|शुक्रिया|थैंक्स)'
    ]
}

class ChatbotProcessor:
    """
    A class to process messages for the context-aware chatbot
    """
    
    def __init__(self):
        self.openai_available = openai.api_key is not None
    
    def detect_language(self, text):
        """
        Detect the language of the input text
        Returns language code ('en', 'hi', etc.)
        """
        try:
            # First try langdetect
            lang = detect(text)
            
            # Simple heuristic for Hindi/English detection
            if any(self._contains_devanagari(text)):
                return 'hi'
            
            return lang
        except:
            # Default to English if detection fails
            return 'en'
    
    def _contains_devanagari(self, text):
        """Check if text contains Devanagari script characters"""
        devanagari_pattern = re.compile(r'[\u0900-\u097F]')
        return devanagari_pattern.findall(text)
    
    def extract_entities(self, text, language='en'):
        """
        Extract entities from text using spaCy or regex patterns
        Returns list of entities
        """
        entities = []
        
        # Extract symptoms using regex
        for symptom in SYMPTOMS:
            if re.search(r'\b' + re.escape(symptom) + r'\b', text.lower()):
                entities.append({
                    'type': 'symptom',
                    'value': symptom,
                    'confidence': 0.8
                })
        
        # Use spaCy for named entity recognition (if available)
        if nlp_en and language == 'en':
            doc = nlp_en(text)
            for ent in doc.ents:
                if ent.label_ in ['DATE', 'TIME', 'GPE', 'ORG', 'PERSON']:
                    entities.append({
                        'type': ent.label_,
                        'value': ent.text,
                        'confidence': 0.7
                    })
        
        return entities
    
    def detect_intent(self, text, language='en'):
        """
        Detect the intent of the user message
        Returns intent name
        """
        text_lower = text.lower()
        
        # Check against intent patterns
        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        
        # Default to general_query if no specific intent is found
        return 'general_query'
    
    def get_sentiment(self, text, language='en'):
        """
        Analyze sentiment of the text
        Returns {'polarity': float, 'subjectivity': float}
        """
        if language == 'en':
            blob = TextBlob(text)
            return {
                'polarity': blob.sentiment.polarity,
                'subjectivity': blob.sentiment.subjectivity
            }
        
        # Default neutral sentiment for non-English text
        return {'polarity': 0, 'subjectivity': 0.5}
    
    def generate_response(self, user_message, conversation_history, user_context):
        """
        Generate a response using OpenAI or fallback mechanisms
        """
        language = self.detect_language(user_message)
        intent = self.detect_intent(user_message, language)
        entities = self.extract_entities(user_message, language)
        
        # Format conversation for OpenAI
        if self.openai_available:
            # Prepare system message based on context
            system_message = self._create_system_message(language, user_context)
            
            # Format conversation history
            messages = [{"role": "system", "content": system_message}]
            
            # Add conversation history
            for msg in conversation_history:
                role = "assistant" if msg.is_bot else "user"
                messages.append({"role": role, "content": msg.content})
            
            try:
                # Call OpenAI API
                response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    max_tokens=350,
                    temperature=0.7,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"OpenAI API error: {str(e)}")
                # Fall back to rule-based responses
        
        # If OpenAI is unavailable or fails, use fallback responses
        return self._generate_fallback_response(user_message, intent, entities, language, user_context)
    
    def _create_system_message(self, language, user_context):
        """Create a system message for the OpenAI API based on context"""
        if language == 'hi':
            return f"""
            आप एक चिकित्सा सहायक हैं जो AyushHealthBot के लिए काम करते हैं। आपका नाम Ayush Assistant है।
            
            आपको निम्नलिखित दिशानिर्देशों का पालन करना चाहिए:
            1. आप हिंदी में बात करेंगे
            2. आप उपयोगकर्ता के पिछले लक्षणों और चिकित्सा इतिहास को याद रखेंगे
            3. उपयोगकर्ता के बताए गए लक्षणों के आधार पर सहायता देंगे
            4. आप पेशेवर चिकित्सा सलाह का प्रतिस्थापन नहीं हैं, गंभीर लक्षणों के लिए हमेशा डॉक्टर को देखने की सलाह देंगे
            5. आयुर्वेदिक उपचार और आधुनिक चिकित्सा दोनों के बारे में जानकारी दे सकते हैं
            6. उत्तर संक्षिप्त, सहायक और चिकित्सकीय रूप से सही होंगे
            
            संदर्भ जानकारी:
            उपयोगकर्ता के अब तक के लक्षण: {', '.join(user_context.get('symptoms', []))}
            पिछली बातचीत में उल्लिखित विषय: {', '.join(user_context.get('topics', []))}
            """
        else:
            return f"""
            You are a medical assistant working for AyushHealthBot. Your name is Ayush Assistant.
            
            You should follow these guidelines:
            1. Remember the user's previous symptoms and medical history
            2. Provide help based on the symptoms described by the user
            3. You are not a replacement for professional medical advice
            4. For serious symptoms, always advise seeing a doctor
            5. You can provide information about both Ayurvedic treatments and modern medicine
            6. Keep responses concise, helpful, and medically sound
            
            Context information:
            User's symptoms so far: {', '.join(user_context.get('symptoms', []))}
            Topics mentioned in previous conversation: {', '.join(user_context.get('topics', []))}
            """
    
    def _generate_fallback_response(self, message, intent, entities, language, context):
        """Generate a rule-based fallback response"""
        # Extract symptoms from entities
        symptoms = [e['value'] for e in entities if e['type'] == 'symptom']
        previous_symptoms = context.get('symptoms', [])
        all_symptoms = list(set(previous_symptoms + symptoms))
        
        # Hindi responses
        if language == 'hi':
            if intent == 'greeting':
                return "नमस्ते! मैं आपका Ayush स्वास्थ्य सहायक हूँ। आप कैसे हैं और मैं आपकी कैसे मदद कर सकता हूँ?"
            
            if intent == 'goodbye':
                return "अलविदा! अच्छे स्वास्थ्य की कामना करता हूँ। जब भी आपको स्वास्थ्य संबंधी सलाह चाहिए, मुझसे पूछ सकते हैं।"
            
            if intent == 'thank':
                return "आपका स्वागत है! कृपया अच्छे स्वास्थ्य के लिए पर्याप्त आराम करें और पानी पीते रहें।"
            
            if intent == 'symptom_report':
                if not symptoms and not previous_symptoms:
                    return "कृपया अपने लक्षणों के बारे में अधिक जानकारी दें ताकि मैं आपकी बेहतर मदद कर सकूँ।"
                
                if symptoms and previous_symptoms:
                    shared_symptoms = set(symptoms).intersection(set(previous_symptoms))
                    new_symptoms = set(symptoms) - set(previous_symptoms)
                    
                    if new_symptoms:
                        return f"मैं देख रहा हूँ कि आपने पहले {', '.join(previous_symptoms)} का उल्लेख किया था, और अब आपको {', '.join(new_symptoms)} भी हो रहा है। ये लक्षण एक साथ आम तौर पर वायरल संक्रमण के संकेत हो सकते हैं। अधिक पानी पिएं और आराम करें। यदि लक्षण बिगड़ जाते हैं, तो डॉक्टर से परामर्श करें।"
                    else:
                        return f"आपने फिर से {', '.join(shared_symptoms)} का उल्लेख किया। क्या आपको कोई अन्य लक्षण भी महसूस हो रहे हैं?"
                
                # New symptoms only
                symptom_responses = {
                    'fever': "बुखार के लिए, पर्याप्त आराम करें और तरल पदार्थ अधिक पिएं। पैरासिटामोल ले सकते हैं। यदि बुखार 102°F से अधिक है या 3 दिनों से अधिक रहता है, तो डॉक्टर से परामर्श करें।",
                    'bukhaar': "बुखार के लिए, पर्याप्त आराम करें और तरल पदार्थ अधिक पिएं। पैरासिटामोल ले सकते हैं। यदि बुखार 102°F से अधिक है या 3 दिनों से अधिक रहता है, तो डॉक्टर से परामर्श करें।",
                    'headache': "सिरदर्द के लिए, आराम करें, पानी पिएं, और अगर आवश्यक हो तो पैरासिटामोल लें। यदि सिरदर्द गंभीर है या बार-बार होता है, तो डॉक्टर से परामर्श करें।",
                    'sirdard': "सिरदर्द के लिए, आराम करें, पानी पिएं, और अगर आवश्यक हो तो पैरासिटामोल लें। यदि सिरदर्द गंभीर है या बार-बार होता है, तो डॉक्टर से परामर्श करें।",
                    'cough': "खांसी के लिए, गर्म पानी पिएं और शहद-नींबू का मिश्रण ले सकते हैं। अदरक और तुलसी की चाय भी फायदेमंद होती है।",
                    'khansi': "खांसी के लिए, गर्म पानी पिएं और शहद-नींबू का मिश्रण ले सकते हैं। अदरक और तुलसी की चाय भी फायदेमंद होती है।",
                    'sore throat': "गले में खराश के लिए, गर्म नमक के पानी से गरारे करें और आराम करें। शहद और अदरक की चाय पी सकते हैं।",
                    'galaa kharaab': "गले में खराश के लिए, गर्म नमक के पानी से गरारे करें और आराम करें। शहद और अदरक की चाय पी सकते हैं।"
                }
                
                for s in symptoms:
                    if s in symptom_responses:
                        return symptom_responses[s]
                
                return f"मैं आपके {', '.join(symptoms)} के लक्षणों को नोट कर लिया है। कृपया पर्याप्त आराम करें और तरल पदार्थ पिएं। यदि लक्षण गंभीर हों या लंबे समय तक रहें, तो डॉक्टर से परामर्श करें।"
            
            if intent == 'medicine_inquiry':
                if not all_symptoms:
                    return "विशेषिक दवाओं के बारे में सलाह देने के लिए, मुझे आपके लक्षणों के बारे में अधिक जानकारी चाहिए। कृपया अपने लक्षणों का वर्णन करें।"
                
                if 'fever' in all_symptoms or 'bukhaar' in all_symptoms:
                    return "बुखार के लिए, पैरासिटामोल (500-650mg) 6 घंटे में एक बार ले सकते हैं। आयुर्वेदिक उपचार में तुलसी, शहद, और हल्दी वाला दूध शामिल है। अधिक जानकारी के लिए डॉक्टर से परामर्श करें।"
                
                if 'headache' in all_symptoms or 'sirdard' in all_symptoms:
                    return "सिरदर्द के लिए, पैरासिटामोल या आइबुप्रोफेन ले सकते हैं। आयुर्वेदिक उपचार में लौंग का तेल लगाना और तुलसी की चाय शामिल है। पर्याप्त पानी पीना न भूलें।"
                
                return "बिना डॉक्टरी सलाह के दवाएं लेने की सिफारिश नहीं की जाती है। आपके लक्षणों के आधार पर, पर्याप्त आराम करें, अधिक पानी पिएं, और यदि लक्षण गंभीर हैं या 2-3 दिनों से अधिक रहते हैं, तो डॉक्टर से परामर्श करें।"
            
            if intent == 'appointment_inquiry':
                return "डॉक्टर से अपॉइंटमेंट बुक करने के लिए, आप अपने डैशबोर्ड पर 'अपॉइंटमेंट बुक करें' बटन पर क्लिक कर सकते हैं। आप विशेषज्ञता के आधार पर डॉक्टर चुन सकते हैं और अपने लिए सुविधाजनक समय निर्धारित कर सकते हैं।"
            
            # Default response
            return "मैं आपकी स्वास्थ्य संबंधी जिज्ञासाओं में मदद करने के लिए यहां हूं। क्या आप कृपया अधिक विवरण दे सकते हैं कि आप किस तरह की जानकारी चाहते हैं?"
        
        # English responses
        else:
            if intent == 'greeting':
                return "Hello! I'm your Ayush Health Assistant. How are you feeling today and how can I help you?"
            
            if intent == 'goodbye':
                return "Goodbye! Wishing you good health. Feel free to ask me whenever you need health advice."
            
            if intent == 'thank':
                return "You're welcome! Please make sure to rest well and stay hydrated for good health."
            
            if intent == 'symptom_report':
                if not symptoms and not previous_symptoms:
                    return "Please provide more details about your symptoms so I can help you better."
                
                if symptoms and previous_symptoms:
                    shared_symptoms = set(symptoms).intersection(set(previous_symptoms))
                    new_symptoms = set(symptoms) - set(previous_symptoms)
                    
                    if new_symptoms:
                        return f"I see that you previously mentioned {', '.join(previous_symptoms)}, and now you're also experiencing {', '.join(new_symptoms)}. These symptoms together typically suggest a viral infection. Stay hydrated and get rest. If symptoms worsen, consult a doctor."
                    else:
                        return f"You've mentioned {', '.join(shared_symptoms)} again. Are you experiencing any other symptoms?"
                
                # New symptoms only
                symptom_responses = {
                    'fever': "For fever, get plenty of rest and drink fluids. You can take paracetamol. If the fever is above 102°F or persists for more than 3 days, consult a doctor.",
                    'headache': "For headache, rest, stay hydrated, and take paracetamol if needed. If the headache is severe or recurrent, consult a doctor.",
                    'cough': "For cough, drink warm water and try honey-lemon mix. Ginger and tulsi tea can also be beneficial.",
                    'sore throat': "For sore throat, gargle with warm salt water and get rest. You can drink honey and ginger tea."
                }
                
                for s in symptoms:
                    if s in symptom_responses:
                        return symptom_responses[s]
                
                return f"I've noted your symptoms of {', '.join(symptoms)}. Please get adequate rest and stay hydrated. If symptoms are severe or persist, consult a doctor."
            
            if intent == 'medicine_inquiry':
                if not all_symptoms:
                    return "To advise on specific medications, I would need more information about your symptoms. Please describe what you're experiencing."
                
                if 'fever' in all_symptoms:
                    return "For fever, you can take paracetamol (500-650mg) every 6 hours. Ayurvedic remedies include tulsi, honey, and turmeric milk. Please consult a doctor for more information."
                
                if 'headache' in all_symptoms:
                    return "For headache, you can take paracetamol or ibuprofen. Ayurvedic remedies include applying clove oil and drinking tulsi tea. Remember to stay hydrated."
                
                return "Taking medications without medical advice is not recommended. Based on your symptoms, get plenty of rest, drink more water, and if symptoms are severe or persist for more than 2-3 days, consult a doctor."
            
            if intent == 'appointment_inquiry':
                return "To book an appointment with a doctor, you can click on the 'Book Appointment' button on your dashboard. You can select doctors based on specialization and schedule a time that's convenient for you."
            
            # Default response
            return "I'm here to help with your health-related queries. Could you please provide more details about what information you're looking for?"
    
    def update_context_from_message(self, text, context):
        """
        Update context based on user message content
        Returns updated context dictionary
        """
        # Initialize context if empty
        if not context:
            context = {
                'symptoms': [],
                'topics': [],
                'sentiment_history': [],
                'created_at': datetime.now().isoformat()
            }
        
        # Extract entities and update symptoms
        entities = self.extract_entities(text, self.detect_language(text))
        for entity in entities:
            if entity['type'] == 'symptom' and entity['value'] not in context['symptoms']:
                context['symptoms'].append(entity['value'])
        
        # Add topic from the first few words
        words = text.lower().split()
        if len(words) > 3:
            topic = " ".join(words[:min(5, len(words))])
            if topic not in context['topics']:
                context['topics'].append(topic)
        
        # Keep lists to a reasonable size
        if len(context['symptoms']) > 10:
            context['symptoms'] = context['symptoms'][-10:]
        if len(context['topics']) > 5:
            context['topics'] = context['topics'][-5:]
        
        # Update timestamp
        context['created_at'] = datetime.now().isoformat()
        
        return context 

    @property
    def last_updated(self):
        # Return created_at if last_updated doesn't exist in database yet
        return getattr(self, '_created_at', self.created_at) 