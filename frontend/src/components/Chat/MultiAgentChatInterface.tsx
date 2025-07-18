import React, { useEffect, useRef, useState } from 'react';
import { useStreamingAIAmplifyChat } from '../../hooks/useAIAmplifyChat';
import { useAgentStatuses } from '../../hooks/useAmplifyGraphQL';
import AgentMessage from './AgentMessage';
import AgentAvatar from './AgentAvatar';
import { AgentType } from '../../types';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { cn, announceToScreenReader } from '../../lib/utils';

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
  const [isInputFocused, setIsInputFocused] = useState(false);

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

  // Agent status monitoring
  const { agents, loading: agentsLoading } = useAgentStatuses();

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
  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      announceToScreenReader('Message sent');
      handleSubmit(e);
    }
  };

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
      case 'connected': return 'bg-green-500';
      case 'connecting': return 'bg-yellow-500 animate-pulse';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-500';
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
      className={cn("chat-container", className)}
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
      <Card className="flex-shrink-0 rounded-none border-x-0 border-t-0">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex-1 min-w-0">
              <CardTitle className="text-lg sm:text-xl font-semibold text-foreground">
                Multi-Agent Customer Support
              </CardTitle>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <div 
                  className={cn("w-2 h-2 rounded-full", getConnectionStatusColor())}
                  aria-hidden="true"
                />
                <span 
                  className="text-sm text-muted-foreground"
                  aria-live="polite"
                  aria-label={`Connection status: ${getConnectionStatusText()}`}
                >
                  {getConnectionStatusText()}
                </span>
                {currentSessionId && (
                  <span className="text-sm text-muted-foreground hidden sm:inline">
                    • Session: {currentSessionId.slice(-8)}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Agent Status Toggle */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAgentStatus(!showAgentStatus)}
                aria-expanded={showAgentStatus}
                aria-controls="agent-status-panel"
                aria-label={`${showAgentStatus ? 'Hide' : 'Show'} agent status panel`}
              >
                {showAgentStatus ? 'Hide' : 'Show'} Agents
              </Button>

              {/* New Session Button */}
              <Button
                size="sm"
                onClick={handleCreateSession}
                disabled={isLoading}
                loading={isLoading}
                loadingText="Creating..."
                aria-label="Create new chat session"
              >
                New Chat
              </Button>
            </div>
          </div>

          {/* Agent Status Panel */}
          {showAgentStatus && (
            <Card 
              id="agent-status-panel"
              className="mt-4 bg-muted/50"
              role="region"
              aria-label="Agent status information"
            >
              <CardContent className="p-4">
                <h3 className="text-sm font-medium text-foreground mb-3">
                  Agent Status
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
                  {agentsLoading ? (
                    <div className="col-span-full text-sm text-muted-foreground">
                      Loading agent status...
                    </div>
                  ) : agents.length > 0 ? (
                    agents.map((agent) => (
                      <div 
                        key={agent.agentId} 
                        className="flex items-center gap-2 p-3 bg-background rounded-lg border transition-smooth hover:shadow-sm"
                        role="group"
                        aria-label={`${agent.type} agent status: ${agent.status}`}
                      >
                        <AgentAvatar agentType={agent.type} size="sm" />
                        <div className="flex-1 min-w-0">
                          <Badge
                            variant={
                              agent.status === 'HEALTHY' ? 'success' :
                              agent.status === 'DEGRADED' ? 'warning' :
                              'destructive'
                            }
                            className="text-2xs"
                          >
                            {agent.status}
                          </Badge>
                          {agent.averageResponseTime && (
                            <div className="text-2xs text-muted-foreground mt-1">
                              {Math.round(agent.averageResponseTime)}ms avg
                            </div>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="col-span-full text-sm text-muted-foreground">
                      No agent status available
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </CardHeader>
      </Card>

      {/* Messages Area */}
      <div 
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {messages.length === 0 && !isStreaming ? (
          <div className="text-center py-8 px-4">
            <div className="text-muted-foreground mb-6">
              <div className="text-lg sm:text-xl mb-4">👋 Welcome to Multi-Agent Support</div>
              <p className="text-sm sm:text-base">Our AI agents are ready to help you with:</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl mx-auto">
              <Card className="p-4 hover:shadow-md transition-smooth cursor-default">
                <div className="flex items-center gap-3">
                  <AgentAvatar agentType={AgentType.ORDER_MANAGEMENT} size="sm" />
                  <span className="text-sm font-medium">Order Management</span>
                </div>
              </Card>
              <Card className="p-4 hover:shadow-md transition-smooth cursor-default">
                <div className="flex items-center gap-3">
                  <AgentAvatar agentType={AgentType.PRODUCT_RECOMMENDATION} size="sm" />
                  <span className="text-sm font-medium">Product Recommendations</span>
                </div>
              </Card>
              <Card className="p-4 hover:shadow-md transition-smooth cursor-default">
                <div className="flex items-center gap-3">
                  <AgentAvatar agentType={AgentType.PERSONALIZATION} size="sm" />
                  <span className="text-sm font-medium">Personalization</span>
                </div>
              </Card>
              <Card className="p-4 hover:shadow-md transition-smooth cursor-default">
                <div className="flex items-center gap-3">
                  <AgentAvatar agentType={AgentType.TROUBLESHOOTING} size="sm" />
                  <span className="text-sm font-medium">Technical Support</span>
                </div>
              </Card>
            </div>
            <p className="text-sm text-muted-foreground mt-6">
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
                className="chat-message-enter"
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
                className="chat-message-streaming"
              />
            )}
          </>
        )}

        {/* Error Display */}
        {error && (
          <Card className="mx-4 border-destructive bg-destructive/10">
            <CardContent className="p-4">
              <div className="text-destructive text-sm" role="alert">
                <strong>Error:</strong> {error.message}
              </div>
            </CardContent>
          </Card>
        )}

        <div ref={messagesEndRef} aria-hidden="true" />
      </div>

      {/* Input Area */}
      <Card className="chat-input-container rounded-none border-x-0 border-b-0">
        <CardContent className="p-4">
          <form onSubmit={handleFormSubmit} className="flex gap-2">
            <Input
              ref={inputRef}
              id="chat-input"
              type="text"
              value={input}
              onChange={handleInputChange}
              onFocus={() => setIsInputFocused(true)}
              onBlur={() => setIsInputFocused(false)}
              placeholder="Type your message..."
              disabled={isLoading || !currentSessionId}
              className={cn(
                "flex-1 transition-smooth",
                isInputFocused && "ring-2 ring-ring"
              )}
              aria-label="Chat message input"
              aria-describedby="input-help"
            />
            <Button
              type="submit"
              disabled={isLoading || !input.trim() || !currentSessionId}
              loading={isLoading}
              loadingText="Sending..."
              aria-label="Send message"
              className="px-6"
            >
              Send
            </Button>
          </form>

          <div id="input-help" className="sr-only">
            Type your message and press Enter or click Send to chat with our AI agents
          </div>

          {!currentSessionId && (
            <div className="mt-3 text-sm text-muted-foreground text-center">
              <Button
                variant="link"
                onClick={handleCreateSession}
                className="p-0 h-auto text-sm"
                aria-label="Create a new chat session to start chatting"
              >
                Create a new session
              </Button>
              {' '}to start chatting
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default MultiAgentChatInterface;
