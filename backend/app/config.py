import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings for the Flask application."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-for-technical-design-assistant')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    GEMINI_MODEL = "gemini-2.5-flash"  # Current default model
    MONDAY_BOARD_ID = "1825117125"  # Board ID for Tapered Enquiry Maintenance
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB max file size

# Redis Configuration
REDIS_URL = os.environ.get('REDIS_URL')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# Celery Configuration
CELERY_CONFIG = {
    'broker_url': CELERY_BROKER_URL,
    'result_backend': CELERY_RESULT_BACKEND,
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    'task_routes': {
        'app.tasks.process_files_async': {'queue': 'file_processing'},
    }
}
