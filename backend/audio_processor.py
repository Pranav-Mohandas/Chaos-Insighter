import numpy as np
import wave
import io
import base64
from scipy import signal

class AudioProcessor:
    def __init__(self, sample_rate=16000, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_buffer = []
        
    def process_audio_chunk(self, audio_data):
        """Process incoming audio chunk"""
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_data)
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Normalize audio
            audio_normalized = self.normalize_audio(audio_array)
            
            # Convert normalized audio back to list for buffer storage
            # But ensure it stays as numpy array for processing
            self.audio_buffer.extend(audio_normalized.tolist())
            
            return audio_normalized
            
        except Exception as e:
            print(f"Error processing audio chunk: {e}")
            return None
    
    def normalize_audio(self, audio_data):
        """Normalize audio data"""
        # Convert to numpy array if it's a list
        if isinstance(audio_data, list):
            audio_data = np.array(audio_data, dtype=np.float32)
        elif audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        # Normalize to [-1, 1]
        if np.max(np.abs(audio_data)) > 0:
            audio_data = audio_data / np.max(np.abs(audio_data))
        
        # Apply low-pass filter to remove noise
        try:
            nyquist = self.sample_rate // 2
            cutoff = min(4000, nyquist - 1)  # 4kHz cutoff
            b, a = signal.butter(4, cutoff / nyquist, btype='low')
            audio_filtered = signal.filtfilt(b, a, audio_data)
            return audio_filtered
        except Exception as e:
            print(f"Filter error: {e}")
            return audio_data  # Return unfiltered if filter fails
    
    def get_audio_for_transcription(self, duration_seconds=5):
        """Get audio chunk for transcription"""
        samples_needed = int(self.sample_rate * duration_seconds)
        
        if len(self.audio_buffer) >= samples_needed:
            # Get the required samples and convert back to numpy array
            audio_chunk = np.array(self.audio_buffer[:samples_needed], dtype=np.float32)
            
            # Remove processed samples from buffer
            self.audio_buffer = self.audio_buffer[samples_needed//2:]  # 50% overlap
            
            # Convert to wav format
            return self.array_to_wav(audio_chunk)
        
        return None
    
    def array_to_wav(self, audio_array):
        """Convert numpy array to WAV bytes"""
        # Convert to 16-bit PCM
        audio_int16 = (audio_array * 32767).astype(np.int16)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 2 bytes per sample
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        wav_buffer.seek(0)
        return wav_buffer.getvalue()
    
    def clear_buffer(self):
        """Clear the audio buffer"""
        self.audio_buffer = []
