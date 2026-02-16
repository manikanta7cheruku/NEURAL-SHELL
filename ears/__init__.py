# ears/__init__.py
# Bridge file — keeps backward compatibility
# V1.2: listen() returns (text, audio_path) tuple
# V1.3: Added listen_for_interrupt for full duplex

from ears.core import listen
from ears.core import listen_for_interrupt