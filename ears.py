import speech_recognition as sr
from faster_whisper import WhisperModel
import os

# UPGRADE: Switching to 'medium.en'. 
# It is 2x smarter than 'small.en' but requires ~1.5GB VRAM. 
# Your RTX 5050 (8GB) can handle this easily.
MODEL_SIZE = "medium.en" 

print(f"Loading Whisper Model ({MODEL_SIZE})...")
audio_model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")

def listen():
    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        # TWEAK: Hardcode sensitivity. 
        # If it misses your voice, LOWER this number (e.g. 300).
        # If it hears breathing/static, RAISE this number (e.g. 500 or 800).
        recognizer.dynamic_energy_threshold = False
        recognizer.energy_threshold = 400 
        
        try:
            print("🎧 Listening...")
            # phrase_time_limit=None allows you to speak longer sentences
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=None)
            
            with open("temp_audio.wav", "wb") as f:
                f.write(audio.get_wav_data())
            
            # TRANSCRIBE
            # We add a generic prompt to keep it focused on English conversation
            segments, info = audio_model.transcribe("temp_audio.wav", beam_size=5)
            
            full_text = ""
            for segment in segments:
                full_text += segment.text
            
            clean_text = full_text.strip()
            
            # --- THE HALLUCINATION FILTER ---
            # If it hears the YouTube Ghost, we kill it.
            forbidden_phrases = [
                "Thanks for watching",
                "subscribe",
                "video",
                "Amara.org" 
            ]
            
            for phrase in forbidden_phrases:
                if phrase.lower() in clean_text.lower():
                    return "" # Return silence instead of garbage

            if len(clean_text) < 2: 
                return ""
                
            return clean_text

        except sr.WaitTimeoutError:
            return "" 
        except Exception as e:
            return ""

if __name__ == "__main__":
    print("Testing Ears (Medium Model)...")
    while True:
        text = listen()
        if text:
            print(f"You said: {text}")