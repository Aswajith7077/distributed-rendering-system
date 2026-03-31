import sys
import os

# Add slave path
sys.path.append(os.path.join(os.getcwd(), 'slave'))

from slave.config import ConfigService

config = ConfigService()
print(f"PUSH_INTERVAL: {config.PUSH_INTERVAL} (Type: {type(config.PUSH_INTERVAL)})")
print(f"RECONNECT_DELAY: {config.RECONNECT_DELAY} (Type: {type(config.RECONNECT_DELAY)})")
print(f"REDIS_PORT: {config.REDIS_PORT} (Type: {type(config.REDIS_PORT)})")
print(f"NODE_TYPE: {config.NODE_TYPE} (Type: {type(config.NODE_TYPE)})")

# Test fallback
print(f"MISSING_KEY (default None): {config.MISSING_KEY}")
