import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import ReactMarkdown from 'react-markdown';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatInterfaceProps {
  disabled: boolean;
  onSendMessage: (message: string) => Promise<string>;
  onReset?: number;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ disabled, onSendMessage, onReset }) => {
  const [message, setMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (onReset) {
      setChatHistory([]);
    }
  }, [onReset]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || disabled || isLoading) return;

    const userMessage = { role: 'user' as const, content: message };
    setChatHistory([...chatHistory, userMessage]);
    setMessage('');
    setIsLoading(true);

    try {
      const response = await onSendMessage(message);
      setChatHistory(prev => [...prev, { role: 'assistant', content: response }]);
    } catch (error) {
      console.error('Error sending message:', error);
      setChatHistory(prev => [...prev, { role: 'assistant', content: 'Sorry, an error occurred.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="shadow-md border-0">
      <CardHeader className="bg-[#b82c25] text-white rounded-t-lg section-header">
        <CardTitle>
          <span className="step-indicator">3</span> Chat with Assistant
        </CardTitle>
      </CardHeader>
      <CardContent className="chat-content">
        <div className="h-80 overflow-y-auto mb-4 p-4 border rounded">
          {chatHistory.length === 0 && (
            <p className="placeholder-text">Ask questions about the extracted parameters</p>
          )}
          {chatHistory.map((msg, index) => (
            <div key={index} className={`mb-2 p-2 rounded ${msg.role === 'user' ? 'bg-blue-100 ml-8' : 'bg-gray-100 mr-8'}`}>
              {msg.role === 'user' ? (
                <p>{msg.content}</p>
              ) : (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              )}
            </div>
          ))}
          {isLoading && (
            <div className="bg-gray-100 p-2 rounded mr-8">
              <p>Thinking...</p>
            </div>
          )}
        </div>
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type a question…"
            disabled={disabled || isLoading}
            className="flex-1"
          />
          <Button 
            type="submit" 
            variant="tapered"
            size="default"
            disabled={disabled || !message.trim() || isLoading}
          >
            Send
          </Button>
        </form>
        {disabled && (
          <p className="mt-2 text-sm text-gray-500">Upload and process files first, then ask follow up questions! 🙂</p>
        )}
      </CardContent>
    </Card>
  );
}; 