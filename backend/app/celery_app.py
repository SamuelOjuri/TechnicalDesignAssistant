from celery import Celery
from flask import Flask
from .config import CELERY_CONFIG

def create_celery_app(app: Flask = None) -> Celery:
    """
    Create and configure Celery app
    """
    celery = Celery(app.import_name if app else 'app')
    celery.conf.update(CELERY_CONFIG)
    
    if app:
        # Update task base class to work with Flask app context
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    return celery
