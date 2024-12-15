import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_default_secret_key'
    DEBUG = os.environ.get('DEBUG', 'False') == 'True'
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('REDIS_URL') or None
    # Add any additional configuration settings as needed