import sys
import os

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now your existing imports will work
from flask import Flask, request
from flask_socketio import SocketIO, emit
import json
import threading
import time
from datetime import datetime
import os

from audio_processor import AudioProcessor
from transcription import TranscriptionService
from insights import InsightsGenerator  # Fixed import name
from shared.config import Config

# Initialize Groq client for insights
from groq import Groq
groq_client = Groq(api_key=Config.API_KEY)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize services
audio_processor = AudioProcessor()
transcription_service = TranscriptionService()
insights_generator = InsightsGenerator(groq_client, Config.MODEL_NAME)  # Pass Groq client

# Global session state
current_session = {
    'active': False,
    'start_time': None,
    'transcript_parts': []
}

def save_session(session_data):
    """Save session data to JSON file"""
    try:
        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(__file__), 'data', 'sessions')
        os.makedirs(data_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{timestamp}.json"
        filepath = os.path.join(data_dir, filename)
        
        # Save session data
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Session saved to {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Error saving session: {e}")
        return None

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('start_session')
def handle_start_session():
    """Start a new transcription session"""
    global current_session
    
    current_session['active'] = True
    current_session['start_time'] = datetime.now()
    current_session['transcript_parts'] = []
    
    # Clear previous data
    audio_processor.clear_buffer()
    insights_generator.clear_buffer()  # Fixed method name
    
    # Start continuous transcription
    transcription_service.start_continuous_transcription(
        audio_processor, 
        handle_new_transcript
    )
    
    print("Session started")
    emit('session_started', {'message': 'Session started successfully'})

@socketio.on('stop_session')
def handle_stop_session():
    """Handle session stop and generate final insights"""
    if not current_session['active']:
        return
    
    try:
        current_session['active'] = False
        
        # Generate comprehensive insights from entire session
        print("🧠 Generating final session insights...")
        final_insights = insights_generator.generate_final_insights()
        
        if final_insights:
            socketio.emit('final_insights', final_insights)
            print(f"✅ Sent final insights to frontend: {len(final_insights.get('insights', []))} insights")
        
        # Save session
        session_data = {
            'transcript_parts': current_session['transcript_parts'],
            'insights': final_insights,
            'session_ended': datetime.now().isoformat()
        }
        
        save_session(session_data)
        socketio.emit('session_stopped', {'message': 'Session ended successfully'})
        
        # Stop transcription
        if transcription_service:
            transcription_service.stop_transcription()
        
    except Exception as e:
        print(f"Error stopping session: {e}")

@socketio.on('audio_data')
def handle_audio_data(data):
    """Handle incoming audio data"""
    if not current_session['active']:
        return
    
    try:
        audio_chunk = data.get('audio')
        if audio_chunk:
            # Process the audio chunk
            processed_audio = audio_processor.process_audio_chunk(audio_chunk)
            
            if processed_audio is not None:
                # Audio processed successfully
                emit('audio_received', {'status': 'ok'})
            
    except Exception as e:
        print(f"Error handling audio data: {e}")
        emit('audio_error', {'error': str(e)})

def handle_new_transcript(text):
    """Handle new transcript text"""
    if not current_session['active']:
        return
    
    try:
        # Add to session transcript
        current_session['transcript_parts'].append({
            'text': text,
            'timestamp': datetime.now().isoformat()
        })
        
        # Update insights generator (accumulate transcript only)
        insights_generator.update_transcript(text)
        
        # Send transcript to frontend
        socketio.emit('new_transcript', {
            'text': text,
            'timestamp': datetime.now().isoformat()
        })
        
        print(f"✅ Sent transcript to frontend: {text[:50]}...")
        
        # NO INSIGHTS GENERATION DURING RECORDING - Wait for session end
        
    except Exception as e:
        print(f"❌ Error handling transcript: {e}")

@app.route('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

if __name__ == '__main__':
    print("Starting Audio Insights Backend...")
    print(f"Groq URL: {Config.API_BASE_URL}")
    print(f"Model: {Config.MODEL_NAME}")
    
    socketio.run(
        app, 
        host=Config.FLASK_HOST, 
        port=Config.FLASK_PORT, 
        debug=True
    )
