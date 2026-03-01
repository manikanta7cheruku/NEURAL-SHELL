# mouth/__init__.py
# Bridge file — keeps backward compatibility
# V1.3: speak, interrupt, is_speaking
# V1.9: speak_streamed for streaming responses

from mouth.core import speak, interrupt, is_speaking, speak_streamed