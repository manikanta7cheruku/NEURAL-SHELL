# ears/__init__.py
# Bridge file — keeps backward compatibility
# main.py still does: from ears import listen
# BUT now listen() returns (text, audio_path) tuple

from ears.core import listen