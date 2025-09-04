import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useStreamingAIAmplifyChat } from '../../hooks/useAIAmplifyChat';
import { useAgentStatuses } from '../../hooks/useAmplifyGraphQL';
import AgentMessage from './AgentMessage';
import AgentAvatar from './AgentAvatar';
import { AgentType } from '../../types';
import { announceToScreenReader } from '../../lib/utils';

interface MultiAgentChatInterfaceProps {
  sessionId?: string;
  className?: string;
  onSessionCreate?: (sessionId: string) => void;
  onAgentResponse?: (agentType: AgentType, message: any) => void;
}

const MultiAgentChatInterface: React.FC<MultiAgentChatInterfaceProps> = ({
  sessionId,
  className = '',
  onSessionCreate,
  onAgentResponse
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [showAgentStatus, setShowAgentStatus] = useState(false);


  // AI Chat integration
  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    error,
    sessionId: currentSessionId,
    createNewSession,
    streamingMessage,
    isStreaming,
    streamingAgentType,
    connectionStatus
  } = useStreamingAIAmplifyChat(sessionId || '', {
    onAgentResponse: (agentType, message) => {
      announceToScreenReader(`New message from ${agentType} agent`);
      onAgentResponse?.(agentType, message);
    },
    onError: (error) => {
      announceToScreenReader(`Error: ${error.message}`);
      console.error('Chat error:', error);
    }
  });

  // Agent status monitoring - ONLY WHEN REQUESTED
  const { agents, loading: agentsLoading, refetch: fetchAgentStatus } = useAgentStatuses();

  // Handle agent status toggle
  const handleAgentStatusToggle = () => {
    const newShowStatus = !showAgentStatus;
    setShowAgentStatus(newShowStatus);
    
    // Only fetch agent status when panel is opened
    if (newShowStatus) {
      fetchAgentStatus();
    }
  };

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage]);

  // Handle session creation
  const handleCreateSession = async () => {
    try {
      const newSessionId = await createNewSession();
      if (newSessionId) {
        announceToScreenReader('New chat session created');
        onSessionCreate?.(newSessionId);
        inputRef.current?.focus();
      }
    } catch (error) {
      console.error('Failed to create session:', error);
      announceToScreenReader('Failed to create new session');
    }
  };



  // Handle form submission with accessibility
  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      announceToScreenReader('Message sent');
      handleSubmit(e);
    }
  };

  // Auto-create session when user starts typing (if no session exists)
  const handleInputChangeWithSessionCreation = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    handleInputChange(e);
    
    // Auto-create session if none exists and user is typing
    if (!currentSessionId && e.target.value.trim() && !isLoading) {
      try {
        const newSessionId = await createNewSession();
        if (newSessionId) {
          announceToScreenReader('New chat session created');
          onSessionCreate?.(newSessionId);
        }
      } catch (error) {
        console.error('Failed to create session:', error);
        // Don't show error to user for background session creation
      }
    }
  }, [handleInputChange, currentSessionId, isLoading, createNewSession, onSessionCreate]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && showAgentStatus) {
      setShowAgentStatus(false);
      inputRef.current?.focus();
    }
  };

  // Connection status indicator
  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'status-connected';
      case 'connecting': return 'status-connecting';
      case 'error': return 'status-error';
      default: return 'status-dot';
    }
  };

  const getConnectionStatusText = () => {
    switch (connectionStatus) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'error': return 'Connection Error';
      default: return 'Disconnected';
    }
  };

  return (
    <div 
      className={`chat-container ${className}`}
      onKeyDown={handleKeyDown}
      role="main"
      aria-label="Multi-Agent Chat Interface"
    >
      {/* Skip link for accessibility */}
      <a 
        href="#chat-input" 
        className="skip-link"
        onFocus={() => announceToScreenReader('Skip to chat input')}
      >
        Skip to chat input
      </a>

      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-content">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="connection-status">
              <div className={`status-dot ${getConnectionStatusColor()}`} aria-hidden="true" />
              <span 
                aria-live="polite"
                aria-label={`Connection status: ${getConnectionStatusText()}`}
              >
                {getConnectionStatusText()}
              </span>
              {currentSessionId && (
                <span className="user-info" style={{ color: '#64748b' }}>
                  • Session: {currentSessionId.slice(-8)}
                </span>
              )}
            </div>
          </div>

          <div className="chat-header-buttons">
            {/* Agent Status Toggle */}
            <button
              className="button button-outline button-sm"
              onClick={handleAgentStatusToggle}
              aria-expanded={showAgentStatus}
              aria-controls="agent-status-panel"
              aria-label={`${showAgentStatus ? 'Hide' : 'Show'} agent status panel`}
            >
              {showAgentStatus ? 'Hide' : 'Show'} Agents
            </button>

            {/* New Session Button */}
            <button
              className="button button-primary button-sm"
              onClick={handleCreateSession}
              disabled={isLoading}
            >
              {isLoading ? 'Creating...' : 'New Chat'}
            </button>
          </div>
        </div>

        {/* Agent Status Panel */}
        {showAgentStatus && (
          <div 
            id="agent-status-panel"
            className="agent-status-panel"
            role="region"
            aria-label="Agent status information"
          >
            <h3 className="agent-status-title">
              Agent Status
            </h3>
            <div className="agent-status-grid">
              {agentsLoading ? (
                <div style={{ gridColumn: '1 / -1', fontSize: '0.875rem', color: '#64748b' }}>
                  Loading agent status...
                </div>
              ) : agents.length > 0 ? (
                agents.map((agent) => (
                  <div 
                    key={agent.agentId} 
                    className="agent-status-card"
                    role="group"
                    aria-label={`${agent.type} agent status: ${agent.status}`}
                  >
                    <AgentAvatar agentType={agent.type} size="sm" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        display: 'inline-block',
                        padding: '0.125rem 0.5rem',
                        fontSize: '0.75rem',
                        fontWeight: '500',
                        borderRadius: '0.375rem',
                        backgroundColor: agent.status === 'HEALTHY' ? '#10b981' : 
                                       agent.status === 'DEGRADED' ? '#f59e0b' : '#ef4444',
                        color: 'white'
                      }}>
                        {agent.status}
                      </div>
                      {agent.averageResponseTime && (
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                          {Math.round(agent.averageResponseTime)}ms avg
                        </div>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ gridColumn: '1 / -1', fontSize: '0.875rem', color: '#64748b' }}>
                  No agent status available
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Messages Area */}
      <div 
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {messages.length === 0 && !isStreaming ? (
          <div className="welcome-screen">
            <div className="welcome-title">
              <div style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>👋 Welcome to Multi-Agent Support</div>
              <p className="welcome-subtitle">Our AI agents are ready to help you with:</p>
            </div>
            <div className="welcome-grid">
              <div className="welcome-card">
                <div className="welcome-card-content">
                  <AgentAvatar agentType={AgentType.ORDER_MANAGEMENT} size="sm" />
                  <span className="welcome-card-text">Order Management</span>
                </div>
              </div>
              <div className="welcome-card">
                <div className="welcome-card-content">
                  <AgentAvatar agentType={AgentType.PRODUCT_RECOMMENDATION} size="sm" />
                  <span className="welcome-card-text">Product Recommendations</span>
                </div>
              </div>
              <div className="welcome-card">
                <div className="welcome-card-content">
                  <AgentAvatar agentType={AgentType.PERSONALIZATION} size="sm" />
                  <span className="welcome-card-text">Personalization</span>
                </div>
              </div>
              <div className="welcome-card">
                <div className="welcome-card-content">
                  <AgentAvatar agentType={AgentType.TROUBLESHOOTING} size="sm" />
                  <span className="welcome-card-text">Technical Support</span>
                </div>
              </div>
            </div>
            <p className="welcome-footer">
              Start typing your question below to get started!
            </p>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <AgentMessage
                key={message.id}
                id={message.id}
                content={message.content}
                role={message.role}
                agentType={message.agentType}
                confidence={message.confidence}
                processingTime={message.processingTime}
                timestamp={message.createdAt}
                metadata={message.metadata}
                className="fade-in"
              />
            ))}

            {/* Streaming Message */}
            {isStreaming && streamingMessage && (
              <AgentMessage
                id="streaming"
                content={streamingMessage}
                role="assistant"
                agentType={streamingAgentType || undefined}
                isStreaming={true}
                className="slide-up"
              />
            )}
          </>
        )}

        {/* Error Display */}
        {error && (
          <div className="error-message" role="alert">
            <strong>Error:</strong> {error.message}
          </div>
        )}

        <div ref={messagesEndRef} aria-hidden="true" />
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        <form onSubmit={handleFormSubmit}>
          <div className="chat-input-form">
            <input
              ref={inputRef}
              id="chat-input"
              type="text"
              value={input}
              onChange={handleInputChangeWithSessionCreation}

              placeholder="Type your message..."
              disabled={isLoading}
              className="chat-input"
              aria-label="Chat message input"
              aria-describedby="input-help"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              aria-label="Send message"
              className="send-button"
            >
              {isLoading ? (
                <div className="animate-spin" style={{
                  width: '1.25rem',
                  height: '1.25rem',
                  border: '2px solid white',
                  borderTopColor: 'transparent',
                  borderRadius: '50%'
                }} />
              ) : (
                <svg style={{ width: '1.25rem', height: '1.25rem' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              )}
            </button>
          </div>
        </form>

        <div id="input-help" className="sr-only">
          Type your message and press Enter or click Send to chat with our AI agents
        </div>


      </div>
    </div>
  );
};

export default MultiAgentChatInterface;
