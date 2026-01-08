import sys
import os

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import socketio
import base64
import numpy as np
import streamlit as st
from shared.config import Config
import threading
import queue

class WebSocketClient:
    def __init__(self):
        self.sio = socketio.Client()
        self.connected = False
        self.transcript_queue = queue.Queue()  # Thread-safe queue
        self.insights_queue = queue.Queue()   # Thread-safe queue
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup WebSocket event handlers"""
        
        @self.sio.event
        def connect():
            self.connected = True
            print("🔗 WebSocket connected successfully")
        
        @self.sio.event
        def disconnect():
            self.connected = False
            print("❌ WebSocket disconnected")
        
        @self.sio.event
        def session_started(data):
            print("✅ Session started")
        
        @self.sio.event
        def session_stopped(data):
            print("⏹️ Session stopped")
        
        @self.sio.event
        def new_transcript(data):
            print(f"📝 Received transcript: {data['text'][:50]}...")
            # Put data in thread-safe queue instead of directly accessing session state
            self.transcript_queue.put({
                'text': data['text'],
                'timestamp': data['timestamp']
            })

        @self.sio.event
        def new_insights(data):
            print(f"💡 Received live insights: {len(data.get('insights', []))} insights")
            # Put data in thread-safe queue (though not used in end-only approach)
            self.insights_queue.put(data)

        @self.sio.event
        def final_insights(data):
            print(f"🎯 Received final insights: {len(data.get('insights', []))} insights")
            # Put final insights in queue
            self.insights_queue.put(data)
        
        @self.sio.event
        def audio_received(data):
            # Audio chunk received successfully
            pass
        
        @self.sio.event
        def audio_error(data):
            print(f"Audio error: {data.get('error', 'Unknown error')}")
    
    def get_new_transcripts(self):
        """Get new transcripts from queue (thread-safe)"""
        transcripts = []
        while not self.transcript_queue.empty():
            try:
                transcripts.append(self.transcript_queue.get_nowait())
            except:
                break
        return transcripts
    
    def get_new_insights(self):
        """Get new insights from queue (thread-safe)"""
        try:
            return self.insights_queue.get_nowait()
        except:
            return None
    
    def connect_to_server(self):
        """Connect to the WebSocket server"""
        try:
            if not self.connected:
                self.sio.connect(f'http://{Config.FLASK_HOST}:{Config.FLASK_PORT}')
                return True
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False
        return self.connected
    
    def disconnect_from_server(self):
        """Disconnect from the WebSocket server"""
        if self.connected:
            self.sio.disconnect()
    
    def start_session(self):
        """Start a new transcription session"""
        if self.connected:
            self.sio.emit('start_session')
    
    def stop_session(self):
        """Stop the current session"""
        if self.connected:
            self.sio.emit('stop_session')
    
    def send_audio_data(self, audio_data):
        """Send audio data to the server"""
        if self.connected:
            # Convert audio to base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            self.sio.emit('audio_data', {'audio': audio_base64})

def audio_to_bytes(audio_array, sample_rate=16000):
    """Convert audio array to bytes"""
    # Ensure audio is in the right format
    if audio_array.dtype != np.int16:
        # Convert to 16-bit PCM
        audio_array = (audio_array * 32767).astype(np.int16)
    
    return audio_array.tobytes()

def format_timestamp(timestamp_str):
    """Format timestamp for display"""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%H:%M:%S")
    except:
        return timestamp_str

def get_session_summary(transcript_parts):
    """Generate a simple summary of transcript parts"""
    if not transcript_parts:
        return "No transcript available"
    
    total_parts = len(transcript_parts)
    total_chars = sum(len(part['text']) for part in transcript_parts)
    
    return f"Session contains {total_parts} transcript segments ({total_chars} characters total)"

