import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import ReactMarkdown from 'react-markdown';
import { Bot, MessageSquareText, Send, UserRound } from 'lucide-react';

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
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (onReset) {
      setChatHistory([]);
    }
  }, [onReset]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isLoading]);

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
    <Card className="section-card chat-panel">
      <CardHeader className="section-header">
        <div className="panel-heading">
          <div>
            <p className="panel-eyebrow">Technical support</p>
            <CardTitle>Ask the assistant</CardTitle>
            <CardDescription>Discuss values, sources, and inconsistencies.</CardDescription>
          </div>
          <span className="assistant-mark" aria-hidden="true"><Bot className="h-4 w-4" /></span>
        </div>
      </CardHeader>
      <CardContent className="chat-content">
        <div className="chat-history" aria-live="polite">
          {chatHistory.length === 0 && (
            <div className="chat-empty">
              <MessageSquareText className="h-7 w-7" aria-hidden="true" />
              <p>Ask a question about the extracted parameters.</p>
              <div className="chat-suggestions">
                {['Summarise the enquiry', 'Which values need review?'].map((suggestion) => (
                  <button key={suggestion} type="button" onClick={() => setMessage(suggestion)} disabled={disabled}>
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}
          {chatHistory.map((msg, index) => (
            <div key={index} className={`chat-message chat-message--${msg.role}`}>
              <span className="chat-avatar" aria-hidden="true">
                {msg.role === 'user' ? <UserRound className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </span>
              <div className="chat-bubble">
                <strong>{msg.role === 'user' ? 'You' : 'Assistant'}</strong>
                {msg.role === 'user' ? <p>{msg.content}</p> : <ReactMarkdown>{msg.content}</ReactMarkdown>}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="chat-message chat-message--assistant">
              <span className="chat-avatar" aria-hidden="true"><Bot className="h-4 w-4" /></span>
              <div className="chat-bubble chat-thinking">
                <span></span><span></span><span></span>
                <span className="sr-only">Assistant is thinking</span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
        <form onSubmit={handleSendMessage} className="chat-composer">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask about the analysis..."
            disabled={disabled || isLoading}
            className="flex-1"
            aria-label="Message the technical assistant"
          />
          <Button 
            type="submit" 
            variant="tapered"
            size="default"
            disabled={disabled || !message.trim() || isLoading}
            className="h-10 w-10 p-0 flex-none"
            title="Send message"
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Send message</span>
          </Button>
        </form>
        {disabled && (
          <p className="mt-2 text-xs text-[#6b6d70]">Process an enquiry to start a conversation.</p>
        )}
      </CardContent>
    </Card>
  );
}; 