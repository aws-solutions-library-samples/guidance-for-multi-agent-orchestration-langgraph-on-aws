import React from 'react';
import { AgentType } from '../../types';
import AgentAvatar from './AgentAvatar';
import AgentBadge from './AgentBadge';

interface AgentMessageProps {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  agentType?: AgentType;
  confidence?: number;
  processingTime?: number;
  timestamp?: Date;
  metadata?: Record<string, any>;
  isStreaming?: boolean;
  className?: string;
}

const AgentMessage: React.FC<AgentMessageProps> = ({
  id,
  content,
  role,
  agentType,
  confidence,
  processingTime,
  timestamp,
  metadata,
  isStreaming = false,
  className = ''
}) => {
  const isUser = role === 'user';
  const isAssistant = role === 'assistant';

  const formatTimestamp = (date: Date) => {
    return date.toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div className={`message-container ${isUser ? 'user' : ''} ${className}`}>
      {/* Avatar */}
      <div className="message-avatar" style={{
        backgroundColor: isUser ? '#3b82f6' : 
                        agentType === AgentType.ORDER_MANAGEMENT ? '#3b82f6' :
                        agentType === AgentType.PRODUCT_RECOMMENDATION ? '#10b981' :
                        agentType === AgentType.PERSONALIZATION ? '#8b5cf6' :
                        agentType === AgentType.TROUBLESHOOTING ? '#ef4444' :
                        agentType === AgentType.SUPERVISOR ? '#6b7280' : '#64748b'
      }}>
        {isUser ? 'U' : 
         agentType === AgentType.ORDER_MANAGEMENT ? 'O' :
         agentType === AgentType.PRODUCT_RECOMMENDATION ? 'P' :
         agentType === AgentType.PERSONALIZATION ? 'Pe' :
         agentType === AgentType.TROUBLESHOOTING ? 'T' :
         agentType === AgentType.SUPERVISOR ? 'S' : 'AI'}
      </div>

      {/* Message Content */}
      <div className={`message-content ${isUser ? 'user' : ''}`}>
        {/* Agent Badge and Metadata */}
        {isAssistant && agentType && (
          <div style={{ 
            marginBottom: '0.25rem',
            alignSelf: isUser ? 'flex-end' : 'flex-start'
          }}>
            <div style={{
              display: 'inline-block',
              padding: '0.125rem 0.5rem',
              fontSize: '0.75rem',
              fontWeight: '500',
              borderRadius: '0.375rem',
              backgroundColor: '#f1f5f9',
              color: '#475569',
              border: '1px solid #e2e8f0'
            }}>
              {agentType.replace('_', ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())}
            </div>
          </div>
        )}

        {/* Message Bubble */}
        <div className={`message-bubble ${isUser ? 'user' : 'agent'} ${isStreaming ? 'streaming' : ''}`}>
          {/* Streaming indicator */}
          {isStreaming && (
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.5rem', 
              marginBottom: '0.5rem', 
              fontSize: '0.875rem', 
              opacity: 0.7 
            }}>
              <div style={{ display: 'flex', gap: '0.25rem' }}>
                <div className="animate-bounce" style={{
                  width: '0.5rem',
                  height: '0.5rem',
                  backgroundColor: 'currentColor',
                  borderRadius: '50%',
                  animationDelay: '0ms'
                }}></div>
                <div className="animate-bounce" style={{
                  width: '0.5rem',
                  height: '0.5rem',
                  backgroundColor: 'currentColor',
                  borderRadius: '50%',
                  animationDelay: '150ms'
                }}></div>
                <div className="animate-bounce" style={{
                  width: '0.5rem',
                  height: '0.5rem',
                  backgroundColor: 'currentColor',
                  borderRadius: '50%',
                  animationDelay: '300ms'
                }}></div>
              </div>
              <span>Agent is typing...</span>
            </div>
          )}

          {/* Message Content */}
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {content}
          </div>
        </div>

        {/* Timestamp and additional metadata */}
        <div className={`message-meta ${isUser ? 'user' : ''}`}>
          {timestamp && formatTimestamp(timestamp)}
          
          {/* Processing time and confidence for agent messages */}
          {isAssistant && (confidence || processingTime) && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
              {confidence && (
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  {Math.round(confidence * 100)}% confident
                </span>
              )}
              {processingTime && (
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  {processingTime.toFixed(2)} s
                </span>
              )}
            </div>
          )}
          
          {/* Additional metadata display */}
          {metadata && Object.keys(metadata).length > 0 && (
            <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: '#94a3b8' }}>
              {metadata.source && (
                <span style={{ marginRight: '0.5rem' }}>via {metadata.source}</span>
              )}
              {metadata.model && (
                <span>• {metadata.model}</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentMessage;
