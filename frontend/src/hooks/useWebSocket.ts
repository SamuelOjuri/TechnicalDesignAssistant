import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';

interface ProgressUpdate {
  job_id: string;
  stage: string;
  current_file: string;
  progress: number;
  message: string;
  timestamp: number;
  result?: any;
  error?: string;
  type?: string;
  result_type?: string;
  content?: string;
}

export const useWebSocket = (jobId: string | null, onProgress: (update: ProgressUpdate) => void) => {
  const socketRef = useRef<Socket | null>(null);
  const [connected, setConnected] = useState(false);
  const onProgressRef = useRef(onProgress);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Update the ref when callback changes
  onProgressRef.current = onProgress;

  useEffect(() => {
    if (!jobId) {
      // Clean up existing connection when no jobId
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
      return;
    }

    // Clear any pending reconnection
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    // Don't create new connection if already connected to same job
    if (socketRef.current?.connected) {
      console.log('WebSocket already connected for job:', jobId);
      return;
    }

    console.log('Establishing WebSocket connection for job:', jobId);

    // Clean up existing connection
    if (socketRef.current) {
      socketRef.current.disconnect();
    }

    // ✅ CORRECT - Normal timeout configuration
    socketRef.current = io(process.env.REACT_APP_API_URL || 'http://localhost:5001', {
      transports: ['websocket'], 
      timeout: 60000,           
      reconnection: false,      
      forceNew: true,
      rememberUpgrade: false    
    });

    const socket = socketRef.current;

    socket.on('connect', () => {
      console.log('✅ WebSocket connected for job:', jobId);
      setConnected(true);
      
      // Join the job room
      socket.emit('join_job', { job_id: jobId });
    });

    socket.on('disconnect', (reason) => {
      console.log('❌ WebSocket disconnected:', reason);
      setConnected(false);
      
      // ✅ SIMPLE - Normal reconnection logic only
      if (reason === 'transport close' || reason === 'transport error') {
        console.log('🔄 Scheduling reconnection in 2 seconds...');
        reconnectTimeoutRef.current = setTimeout(() => {
          if (jobId) {
            console.log('🔄 Attempting to reconnect...');
            setConnected(false); // Trigger re-render
          }
        }, 2000);
      }
    });

    socket.on('progress_update', (data: ProgressUpdate) => {
      console.log('📊 Progress update:', data);
      onProgressRef.current(data);
    });

    socket.on('status', (data) => {
      console.log('ℹ️ Status update:', data);
    });

    socket.on('connect_error', (error) => {
      console.error('❌ Connection error:', error);
      setConnected(false);
    });

    return () => {
      console.log('🧹 Cleaning up WebSocket connection for job:', jobId);
      
      // Clear reconnection timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      if (socket?.connected) {
        socket.emit('leave_job', { job_id: jobId });
        socket.disconnect();
      }
    };
  }, [jobId]); // Only depend on jobId

  return { connected };
};