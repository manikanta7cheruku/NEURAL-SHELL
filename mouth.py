import pyttsx3

def speak(text):
    """
    Function to say text aloud.
    """
    # Print what he is saying (Visual Log)
    print(f"🔊 SEVEN: {text}") 
    
    # Filter out technical commands so he doesn't read them
    if "###" in text:
        return 

    try:
        # FIX: Initialize the engine INSIDE the function.
        # This prevents the "Engine Freeze" bug.
        engine = pyttsx3.init()
        
        # CONFIGURATION
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[0].id) # 0 = Male, 1 = Female
        engine.setProperty('rate', 190)           # Speed
        engine.setProperty('volume', 1.0)         # Volume

        # SPEAK
        engine.say(text)
        engine.runAndWait() # This blocks code until he finishes speaking
        
    except Exception as e:
        print(f"Voice Error: {e}")

# --- UNIT TEST ---
if __name__ == "__main__":
    print("Testing Voice...")
    speak("System online.")
    speak("Honesty setting is ninety percent.")
    speak("Testing sequence three.")