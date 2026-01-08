import whisper
import io
import threading
import time
import numpy as np
import tempfile
import os
import wave
from queue import Queue

class TranscriptionService:
    def __init__(self, model_name="base"):
        print("Loading Whisper model...")
        self.model = whisper.load_model(model_name)
        self.transcription_queue = Queue()
        self.running = False
        
    def transcribe_audio(self, audio_bytes):
        """Transcribe audio bytes to text using NumPy array (avoids temp file issues)"""
        try:
            # Convert BytesIO to numpy array
            if isinstance(audio_bytes, bytes):
                audio_file = io.BytesIO(audio_bytes)
            else:
                audio_file = audio_bytes
                
            # Reset file pointer
            audio_file.seek(0)
            
            # Read WAV data and convert to numpy array
            with wave.open(audio_file, 'rb') as wav_file:
                framerate = wav_file.getframerate()
                frames = wav_file.readframes(wav_file.getnframes())
                
            # Convert to numpy array
            audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            
            # Normalize to [-1, 1] range
            audio_np = audio_np / 32768.0
            
            # Transcribe using numpy array (no temp files needed)
            result = self.model.transcribe(
                audio_np,
                language="en", 
                task="transcribe",
                fp16=False,
                verbose=False
            )
            
            return result["text"].strip()
            
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
    
    def transcribe_audio_fallback(self, audio_bytes):
        """Fallback method using temp files with proper cleanup"""
        try:
            # Handle BytesIO object from AudioProcessor
            if isinstance(audio_bytes, bytes):
                audio_file = io.BytesIO(audio_bytes)
            else:
                audio_file = audio_bytes
            
            # Reset file pointer to beginning
            audio_file.seek(0)
            
            # Create temporary file with proper cleanup
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_file.getvalue())
                tmp_file.flush()
                temp_filename = tmp_file.name
            
            # Transcribe after the file is properly closed
            try:
                result = self.model.transcribe(
                    temp_filename,
                    language="en",
                    task="transcribe",
                    fp16=False,
                    verbose=False
                )
                
                text = result["text"].strip()
                
            finally:
                # Ensure file is deleted even if transcription fails
                try:
                    if os.path.exists(temp_filename):
                        # Add small delay to ensure Whisper releases the file
                        time.sleep(0.1)
                        os.unlink(temp_filename)
                except Exception as cleanup_error:
                    print(f"Warning: Could not delete temp file {temp_filename}: {cleanup_error}")
            
            return text
            
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
    
    def start_continuous_transcription(self, audio_processor, callback):
        """Start continuous transcription in a separate thread"""
        self.running = True
        
        def transcription_worker():
            while self.running:
                try:
                    # Get audio chunk for transcription
                    audio_data = audio_processor.get_audio_for_transcription()
                    
                    if audio_data:
                        # Transcribe the audio
                        text = self.transcribe_audio(audio_data)
                        
                        if text:
                            # Send transcript via callback
                            callback(text)
                    
                    # Increase delay to reduce processing load and file conflicts
                    time.sleep(2.0)  # Increased from 0.5 to 2.0 seconds
                    
                except Exception as e:
                    print(f"Transcription worker error: {e}")
                    time.sleep(1)
        
        # Start transcription thread
        self.transcription_thread = threading.Thread(target=transcription_worker)
        self.transcription_thread.daemon = True
        self.transcription_thread.start()
        print("Continuous transcription started")
    
    def stop_transcription(self):
        """Stop the continuous transcription"""
        self.running = False
        if hasattr(self, 'transcription_thread'):
            self.transcription_thread.join(timeout=2)
        print("Transcription stopped")
    
    def test_transcription(self, test_audio_path=None):
        """Test method to verify transcription is working"""
        try:
            if test_audio_path and os.path.exists(test_audio_path):
                result = self.model.transcribe(test_audio_path)
                print(f"Test transcription: {result['text']}")
                return result['text']
            else:
                print("Transcription service loaded successfully")
                return "Service ready"
        except Exception as e:
            print(f"Test transcription error: {e}")
            return None
