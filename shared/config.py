import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Groq API Configuration
    API_BASE_URL = os.getenv('API_BASE_URL', 'https://api.groq.com/openai/v1')
    API_KEY = os.getenv('API_KEY', 'your-groq-api-key')
    MODEL_NAME = os.getenv('MODEL_NAME', 'llama-3.1-8b-instant')
    
    # Flask Configuration
    FLASK_HOST = os.getenv('FLASK_HOST', 'localhost')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    
    # Audio Configuration
    AUDIO_SAMPLE_RATE = int(os.getenv('AUDIO_SAMPLE_RATE', 16000))
    AUDIO_CHUNK_SIZE = int(os.getenv('AUDIO_CHUNK_SIZE', 1024))
    AUDIO_CHANNELS = 1
    AUDIO_FORMAT = 16
    
    # WebSocket Configuration
    WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', 'ws://localhost:5000')
    
    # Session Configuration
    SESSION_DATA_PATH = 'data/sessions'
    
    # Insights Prompts
    INSIGHTS_PROMPT = """
    Analyze the following meeting transcript and extract:
    1. Key Points (main topics discussed)
    2. Action Items (tasks assigned or decisions made)
    3. Important Decisions
    4. Summary (brief overview of the meeting)
    
    Transcript: {transcript}
    
    Format the response as JSON with keys: key_points, action_items, decisions, summary
    """
