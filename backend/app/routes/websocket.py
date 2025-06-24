from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
import redis
import json
import threading
import time
from ..config import REDIS_URL

# ✅ CORRECT - Normal WebSocket configuration (no need for massive timeouts)
socketio = SocketIO(
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,       # Back to 1 minute (was 120)
    ping_interval=25,      # Keep at 25s
    logger=True,          
    engineio_logger=True,
)

# Dedicated connection pool for WebSocket (separate from processing)
websocket_redis_pool = redis.ConnectionPool.from_url(
    REDIS_URL, 
    max_connections=8,  # Conservative limit for WebSocket
    retry_on_timeout=True,
    socket_connect_timeout=5
)
redis_client = redis.Redis(connection_pool=websocket_redis_pool)

# Track active stream workers to prevent duplicates
active_workers = {}
worker_lock = threading.Lock()

@socketio.on('connect')
def on_connect():
    """Handle client connection."""
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_job')
def on_join(data):
    """Join a room for a specific job to receive updates."""
    job_id = data['job_id']
    join_room(job_id)
    emit('status', {'message': f'Joined room for job {job_id}'})
    
    # Only start ONE stream worker per job_id, regardless of how many clients join
    with worker_lock:
        if job_id not in active_workers:
            print(f"Starting stream worker for job_id: {job_id}")
            active_workers[job_id] = True
            start_streaming_updates(job_id)
        else:
            print(f"Stream worker already exists for job_id: {job_id}")

@socketio.on('leave_job')
def on_leave(data):
    """Leave a job room."""
    job_id = data['job_id']
    leave_room(job_id)
    emit('status', {'message': f'Left room for job {job_id}'})

def start_streaming_updates(job_id):
    """Start streaming Redis updates to WebSocket clients."""
    def stream_worker():
        stream_key = f"stream:{job_id}"
        last_id = '0-0'
        
        print(f"Stream worker started for job_id: {job_id}")
        
        try:
            while job_id in active_workers:
                try:
                    # Read new messages from Redis stream
                    messages = redis_client.xread({stream_key: last_id}, block=1000, count=10)
                    
                    if messages:
                        for stream, msgs in messages:
                            for msg_id, fields in msgs:
                                # Convert Redis data to dict
                                data = {k.decode(): v.decode() for k, v in fields.items()}
                                
                                # Emit to WebSocket room (all clients in the room will receive this)
                                socketio.emit('progress_update', data, room=job_id)
                                
                                last_id = msg_id.decode()
                    
                except redis.ResponseError:
                    # Stream doesn't exist yet, continue polling
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Error in stream worker for job_id {job_id}: {e}")
                    break
        finally:
            # Clean up when worker stops
            with worker_lock:
                active_workers.pop(job_id, None)
            print(f"Stream worker stopped for job_id: {job_id}")
    
    # Start worker thread
    thread = threading.Thread(target=stream_worker, name=f"StreamWorker-{job_id}")
    thread.daemon = True
    thread.start()

def stop_streaming_updates(job_id):
    """Stop streaming updates for a job."""
    with worker_lock:
        if job_id in active_workers:
            active_workers.pop(job_id)
            print(f"Requested stop for stream worker: {job_id}")
