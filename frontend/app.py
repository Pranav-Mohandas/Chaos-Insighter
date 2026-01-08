import sys
import os

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import streamlit as st
import pyaudio
import numpy as np
import threading
import time
from utils import WebSocketClient, audio_to_bytes, format_timestamp, get_session_summary
from shared.config import Config
import queue
import sounddevice as sd

# Page configuration
st.set_page_config(
    page_title="Audio Insights System",
    page_icon="🎙️",
    layout="wide"
)

# Initialize session state
if 'ws_client' not in st.session_state:
    st.session_state.ws_client = WebSocketClient()
if 'session_active' not in st.session_state:
    st.session_state.session_active = False
if 'transcript_parts' not in st.session_state:
    st.session_state.transcript_parts = []
if 'current_insights' not in st.session_state:
    st.session_state.current_insights = None
if 'connection_status' not in st.session_state:
    st.session_state.connection_status = "Disconnected"
if 'status_message' not in st.session_state:
    st.session_state.status_message = ""
if 'audio_recording' not in st.session_state:
    st.session_state.audio_recording = False
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

class SystemAudioRecorder:
    def __init__(self):
        self.sample_rate = Config.AUDIO_SAMPLE_RATE
        self.channels = 1  # Mono
        self.audio_queue = queue.Queue()
        self.recording = False
        
    def list_audio_devices(self):
        """List all available audio devices"""
        devices = sd.query_devices()
        print("Available Audio Devices:")
        for i, device in enumerate(devices):
            print(f"{i}: {device['name']} - {device['max_input_channels']} in, {device['max_output_channels']} out")
        return devices
    
    def find_loopback_device(self):
        """Find Windows loopback device or stereo mix"""
        devices = sd.query_devices()
        
        # Look for common loopback device names
        loopback_names = [
            'stereo mix', 'what u hear', 'wave out mix', 
            'loopback', 'speakers', 'headphones'
        ]
        
        for i, device in enumerate(devices):
            device_name = device['name'].lower()
            if any(name in device_name for name in loopback_names):
                if device['max_input_channels'] > 0:
                    print(f"Found potential loopback device: {device['name']}")
                    return i
        
        # If no specific loopback found, use default input device
        return sd.default.device[0]
    
    def start_recording(self, ws_client):
        """Start system audio recording"""
        try:
            # Find the best audio input device
            device_id = self.find_loopback_device()
            
            self.recording = True
            
            def audio_callback(indata, frames, time, status):
                if status:
                    print(f"Audio callback status: {status}")
                
                if self.recording:
                    # Convert to mono if stereo
                    if indata.shape[1] > 1:
                        audio_data = np.mean(indata, axis=1)
                    else:
                        audio_data = indata[:, 0]
                    
                    # Convert to int16
                    audio_int16 = (audio_data * 32767).astype(np.int16)
                    self.audio_queue.put(audio_int16)
            
            # Start recording stream
            self.stream = sd.InputStream(
                device=device_id,
                channels=2,  # Stereo input, convert to mono in callback
                samplerate=self.sample_rate,
                callback=audio_callback,
                blocksize=Config.AUDIO_CHUNK_SIZE
            )
            
            self.stream.start()
            
            # Start audio sender thread
            self.sender_thread = threading.Thread(
                target=self._audio_sender, 
                args=(ws_client,)
            )
            self.sender_thread.daemon = True
            self.sender_thread.start()
            
            print(f"Started recording from device: {sd.query_devices(device_id)['name']}")
            return True
            
        except Exception as e:
            print(f"Failed to start system audio recording: {e}")
            st.error(f"Audio recording error: {e}")
            return False
    
    def stop_recording(self):
        """Stop system audio recording"""
        self.recording = False
        
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
    
    def _audio_sender(self, ws_client):
        """Send audio data to WebSocket server"""
        while self.recording:
            try:
                if not self.audio_queue.empty():
                    audio_data = self.audio_queue.get()
                    audio_bytes = audio_data.tobytes()
                    ws_client.send_audio_data(audio_bytes)
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Error sending audio: {e}")
                time.sleep(0.1)
    
    def cleanup(self):
        """Cleanup audio resources"""
        self.stop_recording()

# Initialize audio recorder
if 'audio_recorder' not in st.session_state:
    st.session_state.audio_recorder = SystemAudioRecorder()

# Main UI
st.title("🎙️Audio Insights")
st.markdown("Capture and analyze audio from meetings, videos, or any system sound")

# Connection status
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown(f"**Status:** {st.session_state.connection_status}")
with col2:
    if st.button("Connect" if st.session_state.connection_status == "Disconnected" else "Disconnect"):
        if st.session_state.connection_status == "Disconnected":
            if st.session_state.ws_client.connect_to_server():
                st.session_state.connection_status = "Connected"
                st.rerun()
        else:
            st.session_state.ws_client.disconnect_from_server()
            st.session_state.connection_status = "Disconnected"
            st.rerun()

# Status message
if st.session_state.status_message:
    st.success(st.session_state.status_message)

# Debug information (can be removed later)
if st.session_state.connection_status == "Connected":
    with st.expander("🔍 Debug Info"):
        st.write(f"Session Active: {st.session_state.session_active}")
        st.write(f"Transcript Parts: {len(st.session_state.transcript_parts)}")
        st.write(f"Current Insights: {'Yes' if st.session_state.current_insights else 'No'}")
        if st.session_state.transcript_parts:
            st.write("Last transcript:", st.session_state.transcript_parts[-1]['text'][:100] + "...")

# Main controls
st.markdown("---")
col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    if st.button("🔊 Start System Recording", disabled=(st.session_state.connection_status != "Connected")):
        if not st.session_state.session_active:
            # Clear previous data
            st.session_state.transcript_parts = []
            st.session_state.current_insights = None
            
            # Start WebSocket session
            st.session_state.ws_client.start_session()
            
            # Start system audio recording
            if st.session_state.audio_recorder.start_recording(st.session_state.ws_client):
                st.session_state.audio_recording = True
                st.session_state.session_active = True
                st.rerun()

with col2:
    if st.button("⏹️ Stop Recording", disabled=not st.session_state.session_active):
        if st.session_state.session_active:
            # Stop audio recording
            st.session_state.audio_recorder.stop_recording()
            st.session_state.audio_recording = False
            
            # Stop WebSocket session
            st.session_state.ws_client.stop_session()
            st.session_state.session_active = False
            st.rerun()

with col3:
    if st.button("🔄 Manual Refresh"):
        st.rerun()

with col4:
    if st.session_state.session_active:
        st.markdown("🔴 **Recording system audio...**")
    else:
        st.markdown("⚫ **Not recording**")

# Check for new data from WebSocket queues (thread-safe)
if st.session_state.connection_status == "Connected":
    # Get new transcripts from queue
    new_transcripts = st.session_state.ws_client.get_new_transcripts()
    if new_transcripts:
        st.session_state.transcript_parts.extend(new_transcripts)
        print(f"✅ Added {len(new_transcripts)} new transcripts to session state")
    
    # Get new insights from queue
    new_insights = st.session_state.ws_client.get_new_insights()
    if new_insights:
        st.session_state.current_insights = new_insights
        print(f"✅ Updated insights in session state")
        st.rerun()

# Session Summary (appears after recording stops)
if not st.session_state.session_active and st.session_state.transcript_parts:
    st.markdown("---")
    st.subheader("📊 Session Complete")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("**📈 Session Statistics:**")
        summary_stats = get_session_summary(st.session_state.transcript_parts)
        st.info(summary_stats)
        
        # Basic statistics only
        total_words = sum(len(part['text'].split()) for part in st.session_state.transcript_parts)
        st.markdown(f"**Total Words:** {total_words}")
        
        # Duration calculation
        if len(st.session_state.transcript_parts) >= 2:
            from datetime import datetime
            try:
                start_time = datetime.fromisoformat(st.session_state.transcript_parts[0]['timestamp'])
                end_time = datetime.fromisoformat(st.session_state.transcript_parts[-1]['timestamp'])
                duration = end_time - start_time
                st.markdown(f"**Session Duration:** {duration}")
            except:
                pass
    
    with col2:
        st.markdown("**🎯 Quick Actions:**")
        if st.button("🔄 Start New Session"):
            st.session_state.transcript_parts = []
            st.session_state.current_insights = None
            st.session_state.status_message = ""
            st.rerun()
    
    st.markdown("---")

# Main content area
st.markdown("---")

# Create two columns for transcript and insights
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 Live Transcript")
    
    transcript_container = st.container()
    with transcript_container:
        if st.session_state.transcript_parts:
            # Display transcript parts
            st.write(f"**Total transcripts received: {len(st.session_state.transcript_parts)}**")
            for i, part in enumerate(st.session_state.transcript_parts[-10:]):  # Show last 10 parts
                timestamp = format_timestamp(part['timestamp'])
                st.markdown(f"**{timestamp}:** {part['text']}")
        else:
            st.info("Start recording to see live transcript...")

with col2:
    st.subheader("💡 Session Insights")
    
    insights_container = st.container()
    with insights_container:
        if st.session_state.current_insights:
            insights = st.session_state.current_insights
            
            # Show final insights indicator
            st.success("🎯 **Final Session Insights**")
            
            # Display insights list
            insights_list = insights.get('insights', [])
            if insights_list and len(insights_list) > 0:
                for i, insight in enumerate(insights_list, 1):
                    if insight and insight.strip():
                        st.markdown(f"**{i}.** {insight}")
            else:
                st.info("No insights were generated from this session")
                
        else:
            if st.session_state.session_active:
                st.info("📝 Insights will be generated when recording stops...")
            else:
                st.info("🎙️ Start recording to capture audio for insights...")

# Smart auto-refresh - only refresh every 3 seconds when session is active
if st.session_state.session_active:
    current_time = time.time()
    if current_time - st.session_state.last_refresh > 3:  # 3 second interval
        st.session_state.last_refresh = current_time
        st.rerun()

# Cleanup on app termination
import atexit
def cleanup():
    if 'audio_recorder' in st.session_state:
        st.session_state.audio_recorder.cleanup()
    if 'ws_client' in st.session_state:
        st.session_state.ws_client.disconnect_from_server()

atexit.register(cleanup)
