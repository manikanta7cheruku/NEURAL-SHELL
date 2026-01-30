import speech_recognition as sr
from faster_whisper import WhisperModel
import os

# CONFIGURATION
# Keep 'small.en' for speed, or 'medium.en' for accuracy.
MODEL_SIZE = "small.en" 

print(f"Loading Whisper Model ({MODEL_SIZE})...")
# device="cuda" means USE YOUR GPU. compute_type="float16" is standard for GPU.
audio_model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")

def listen():
    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        # 1. DYNAMIC CALIBRATION (The Fix for Noisy Rooms)
        # Instead of a hardcoded number, we ask Python to listen to the room first.
        # It sets the "Floor" (background noise level).
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        # 2. ENABLE DYNAMIC ADJUSTMENT
        # True = Automatically raise sensitivity in loud rooms.
        recognizer.dynamic_energy_threshold = True
        
        # 3. SETTINGS FOR CROWDS
        # pause_threshold: How long silence must be to consider the sentence "done".
        # In noise, we want this shorter so he stops listening faster.
        recognizer.pause_threshold = 0.6 
        
        try:
            # We don't print "Listening" inside the function anymore to avoid spam
            # The Main loop handles the UI updates.
            
            # Listen
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=8)
            
            # Save to temporary file
            with open("temp_audio.wav", "wb") as f:
                f.write(audio.get_wav_data())
            
            # Transcribe
            segments, info = audio_model.transcribe("temp_audio.wav", beam_size=5)
            
            full_text = ""
            for segment in segments:
                full_text += segment.text
            
            clean_text = full_text.strip()
            
            # --- HALLUCINATION FILTERS ---
            # In noisy rooms, Whisper might try to interpret noise as words.
            forbidden = [
                "Thanks for watching", "subscribe", "video", 
                "Amara.org", "Caption", "subtitle"
            ]
            
            if len(clean_text) < 2: return ""
            
            for phrase in forbidden:
                if phrase.lower() in clean_text.lower():
                    return ""
                
            return clean_text

        except sr.WaitTimeoutError:
            return "" 
        except Exception as e:
            # print(f"Ear Error: {e}") # Uncomment only for debugging
            return ""

# --- UNIT TEST ---
if __name__ == "__main__":
    print("Testing Ears in Noise...")
    while True:
        text = listen()
        if text:
            print(f"You said: {text}")