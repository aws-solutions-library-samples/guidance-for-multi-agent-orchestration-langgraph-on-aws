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
    <div className={`flex gap-3 p-4 ${isUser ? 'flex-row-reverse' : 'flex-row'} ${className}`}>
      {/* Avatar */}
      <div className="flex-shrink-0">
        {isUser ? (
          <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
            U
          </div>
        ) : agentType ? (
          <AgentAvatar agentType={agentType} size="md" />
        ) : (
          <div className="w-8 h-8 bg-gray-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
            AI
          </div>
        )}
      </div>

      {/* Message Content */}
      <div className={`flex-1 max-w-[70%] ${isUser ? 'text-right' : 'text-left'}`}>
        {/* Agent Badge and Metadata */}
        {isAssistant && agentType && (
          <div className={`mb-2 ${isUser ? 'flex justify-end' : 'flex justify-start'}`}>
            <AgentBadge 
              agentType={agentType}
              confidence={confidence}
              processingTime={processingTime}
              showMetrics={true}
            />
          </div>
        )}

        {/* Message Bubble */}
        <div 
          className={`
            relative
            px-4 
            py-3 
            rounded-2xl 
            ${isUser 
              ? 'bg-blue-500 text-white ml-auto' 
              : 'bg-gray-100 text-gray-900'
            }
            ${isStreaming ? 'animate-pulse' : ''}
          `}
        >
          {/* Streaming indicator */}
          {isStreaming && (
            <div className="flex items-center gap-2 mb-2 text-sm opacity-70">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
              <span>Agent is typing...</span>
            </div>
          )}

          {/* Message Content */}
          <div className="whitespace-pre-wrap break-words">
            {content}
          </div>

          {/* Message tail */}
          <div 
            className={`
              absolute 
              top-4 
              w-3 
              h-3 
              transform 
              rotate-45 
              ${isUser 
                ? 'bg-blue-500 -right-1' 
                : 'bg-gray-100 -left-1'
              }
            `}
          />
        </div>

        {/* Timestamp and additional metadata */}
        <div className={`mt-2 text-xs text-gray-500 ${isUser ? 'text-right' : 'text-left'}`}>
          {timestamp && formatTimestamp(timestamp)}
          
          {/* Additional metadata display */}
          {metadata && Object.keys(metadata).length > 0 && (
            <div className="mt-1 text-xs text-gray-400">
              {metadata.source && (
                <span className="mr-2">via {metadata.source}</span>
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
