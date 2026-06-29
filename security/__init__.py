import os
import sys

_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

_backend_sec = os.path.join(_backend_path, 'security')
if _backend_sec not in __path__:
    __path__.append(_backend_sec)
