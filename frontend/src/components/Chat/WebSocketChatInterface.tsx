import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSessionManagement } from '../../hooks/useSessionManagement';
import { useMessagePersistence } from '../../hooks/useMessagePersistence';
import { useSupervisorAgentEvents } from '../../hooks/useSupervisorAgentEvents';
import AgentMessage from './AgentMessage';
import AgentAvatar from './AgentAvatar';
import { AgentType } from '../../types';
import { announceToScreenReader } from '../../lib/utils';

interface WebSocketChatInterfaceProps {
    initialSessionId?: string;
    className?: string;
    onSessionCreate?: (sessionId: string) => void;
    onAgentResponse?: (agentType: AgentType, message: any) => void;
}

const WebSocketChatInterface: React.FC<WebSocketChatInterfaceProps> = ({
    initialSessionId,
    className = '',
    onSessionCreate,
    onAgentResponse
}) => {
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const [input, setInput] = useState('');
    const processedMessagesRef = useRef<Set<string>>(new Set());
    const [agentProgress, setAgentProgress] = useState<Array<{ id: string, agentType: string, data: any, timestamp: string }>>([]);

    // Session management (reused logic)
    const {
        sessionId,
        createNewSession,
        isCreating,
        error: sessionError
    } = useSessionManagement(initialSessionId);

    // Message persistence (reused logic)
    const {
        messages: persistentMessages,
        saveUserMessage,
        saveAgentMessage,
        loadMessages,
        isLoading: messagesLoading,
        error: messagesError
    } = useMessagePersistence();

    // Amplify Events integration with supervisor agent
    const {
        messages: realtimeMessages,
        publishCustomerRequest,
        isProcessing,
        streamingContent,
        streamingAgentType,
        connectionStatus,
        clearMessages: clearRealtimeMessages
    } = useSupervisorAgentEvents(sessionId);

    // Load messages when session changes
    useEffect(() => {
        if (sessionId) {
            loadMessages(sessionId);
        }
    }, [sessionId, loadMessages]);

    // Handle real-time message processing and save completed responses
    useEffect(() => {
        realtimeMessages.forEach(async (message) => {
            console.log(message)

            // Create unique message ID for deduplication
            const messageId = `${message.type}-${message.timestamp || Date.now()}-${JSON.stringify(message.data?.synthesizer?.synthesized_response || '').slice(0, 50)}`;

            // Skip if already processed
            if (processedMessagesRef.current.has(messageId)) {
                console.log('Skipping duplicate message:', messageId);
                return;
            }

            // Mark as processed
            processedMessagesRef.current.add(messageId);

            switch (message.type) {
                case 'processing_started':
                case 'request_processing_started':
                    announceToScreenReader('Processing started');
                    break;

                case 'progress':
                    // Handle agent progress messages
                    if (message.data) {
                        // Add new progress entries for each agent type in the message data
                        const newProgressEntries: Array<{ id: string, agentType: string, data: any, timestamp: string }> = [];

                        Object.keys(message.data).forEach(agentType => {
                            if (agentType !== 'synthesizer') {
                                const progressEntry = {
                                    id: `${agentType}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                                    agentType: agentType,
                                    data: {
                                        ...message.data[agentType],
                                        status: 'processing'
                                    },
                                    timestamp: message.timestamp || new Date().toISOString()
                                };
                                newProgressEntries.push(progressEntry);
                            }
                        });

                        if (newProgressEntries.length > 0) {
                            setAgentProgress(prev => [...prev, ...newProgressEntries]);
                            announceToScreenReader(`Progress update from ${newProgressEntries.map(e => e.agentType).join(', ')} agent(s)`);
                        }

                        // Handle synthesizer progress messages (no persistence, just UI updates)
                        if (message.data?.synthesizer) {
                            const synthesizer = message.data.synthesizer;
                            announceToScreenReader(`Response in progress: ${synthesizer.synthesized_response?.substring(0, 50)}...`);
                        }
                    }
                    break;

                case 'processing_complete':
                    // Handle final synthesized response
                    if (message.data?.synthesizer) {
                        const synthesizer = message.data.synthesizer;
                        announceToScreenReader(`Processing complete: ${synthesizer.synthesized_response?.substring(0, 50)}...`);

                        // Save final synthesized response to database
                        if (synthesizer.synthesized_response && sessionId) {
                            try {
                                await saveAgentMessage(
                                    synthesizer.synthesized_response,
                                    sessionId,
                                    AgentType.SUPERVISOR,
                                    {
                                        processingTime: synthesizer.processing_time,
                                        completedAt: new Date().toISOString()
                                    }
                                );
                            } catch (error) {
                                console.error('Failed to save final synthesizer message:', error);
                            }
                        }

                        // Notify parent component with final synthesizer data
                        if (onAgentResponse) {
                            onAgentResponse(AgentType.SUPERVISOR, {
                                response: synthesizer.synthesized_response,
                                processing_time: synthesizer.processing_time,
                                messages: synthesizer.messages
                            });
                        }
                    }
                    break;

                case 'request_processing_complete':
                    announceToScreenReader(`Response completed from ${message.agentType} agent`);

                    // Save completed response to database
                    if (message.data?.response && sessionId && message.agentType) {
                        try {
                            await saveAgentMessage(
                                message.data.response,
                                sessionId,
                                message.agentType,
                                {
                                    processingTime: message.data.processing_time,
                                    completedAt: new Date().toISOString()
                                }
                            );
                        } catch (error) {
                            console.error('Failed to save agent message:', error);
                        }
                    }

                    // Notify parent component
                    if (onAgentResponse && message.agentType) {
                        onAgentResponse(message.agentType as AgentType, message.data);
                    }
                    break;

                case 'error':
                case 'request_processing_error':
                case 'agent_error':
                    announceToScreenReader(`Error: ${message.data?.error || 'Processing failed'}`);
                    break;

                case 'token':
                    // Streaming tokens are handled in the hook
                    break;

                default:
                    console.log('Unhandled message type:', message.type);
            }
        });
    }, [realtimeMessages, sessionId, saveAgentMessage, onAgentResponse]);

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [persistentMessages, streamingContent]);

    // Handle session creation (adapted from existing)
    const handleCreateSession = async () => {
        try {
            const newSessionId = await createNewSession();
            announceToScreenReader('New chat session created');
            onSessionCreate?.(newSessionId);
            clearRealtimeMessages();
            inputRef.current?.focus();
        } catch (error) {
            console.error('Failed to create session:', error);
            announceToScreenReader('Failed to create new session');
        }
    };

    // Handle form submission
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isProcessing || !sessionId) return;

        const messageContent = input.trim();
        setInput('');

        try {
            // Save user message to database
            await saveUserMessage(messageContent, sessionId);

            // Publish to supervisor agent via Amplify Events
            await publishCustomerRequest(messageContent, sessionId, {
                timestamp: new Date().toISOString(),
                source: 'WebSocketChatInterface'
            });

            announceToScreenReader('Message sent');
        } catch (error) {
            console.error('Failed to send message:', error);
            announceToScreenReader('Failed to send message');
            // Restore input on error
            setInput(messageContent);
        }
    };

    // Auto-create session when user starts typing (adapted from existing)
    const handleInputChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
        setInput(e.target.value);

        // Auto-create session if none exists and user is typing
        if (!sessionId && e.target.value.trim() && !isCreating) {
            try {
                const newSessionId = await createNewSession();
                announceToScreenReader('New chat session created');
                onSessionCreate?.(newSessionId);
            } catch (error) {
                console.error('Failed to create session:', error);
                // Don't show error to user for background session creation
            }
        }
    }, [sessionId, isCreating, createNewSession, onSessionCreate]);

    // Connection status display
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
    }; return (
        <div
            className={`chat-layout ${className}`}
            role="main"
            aria-label="Multi-Agent Chat Interface"
            style={{ display: 'flex', height: '100%', gap: '1rem' }}
        >
            {/* Chat Panel */}
            <div
                className="chat-container"
                style={{ flex: '2', minWidth: '400px', display: 'flex', flexDirection: 'column' }}
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
                                {sessionId && (
                                    <span className="user-info" style={{ color: '#64748b' }}>
                                        • Session: {sessionId.slice(-8)}
                                    </span>
                                )}
                            </div>
                        </div>

                        <div className="chat-header-buttons">
                            <button
                                className="button button-primary button-sm"
                                onClick={handleCreateSession}
                                disabled={isCreating}
                            >
                                {isCreating ? 'Creating...' : 'New Chat'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Messages Area */}
                <div
                    className="chat-messages"
                    role="log"
                    aria-live="polite"
                    aria-label="Chat messages"
                >
                    {persistentMessages.length === 0 && !streamingContent ? (
                        <div className="welcome-screen">
                            <div className="welcome-title">
                                <div style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>
                                    👋 Welcome to Multi-Agent Support
                                </div>
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
                            {/* Persistent Messages */}
                            {persistentMessages.map((message) => (
                                <AgentMessage
                                    key={message.id}
                                    id={message.id}
                                    content={message.content}
                                    role={message.role}
                                    agentType={message.agentType}

                                    processingTime={message.processingTime}
                                    timestamp={new Date(message.createdAt)}
                                    metadata={message.metadata}
                                    className="fade-in"
                                />
                            ))}

                            {/* Streaming Message */}
                            {streamingContent && (
                                <AgentMessage
                                    id="streaming"
                                    content={streamingContent}
                                    role="assistant"
                                    agentType={streamingAgentType || undefined}
                                    isStreaming={true}
                                    className="slide-up"
                                />
                            )}
                        </>
                    )}

                    {/* Error Display */}
                    {(sessionError || messagesError) && (
                        <div className="error-message" role="alert">
                            <strong>Error:</strong> {
                                sessionError?.message ||
                                messagesError?.message ||
                                'An error occurred'
                            }
                        </div>
                    )}

                    <div ref={messagesEndRef} aria-hidden="true" />
                </div>

                {/* Input Area */}
                <div className="chat-input-area">
                    <form onSubmit={handleSubmit}>
                        <div className="chat-input-form">
                            <input
                                ref={inputRef}
                                id="chat-input"
                                type="text"
                                value={input}
                                onChange={handleInputChange}
                                placeholder="Type your message..."
                                disabled={isProcessing || messagesLoading}
                                className="chat-input"
                                aria-label="Chat message input"
                                aria-describedby="input-help"
                            />
                            <button
                                type="submit"
                                disabled={isProcessing || !input.trim() || !sessionId}
                                aria-label="Send message"
                                className="send-button"
                            >
                                {isProcessing ? (
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

            {/* Progress Panel */}
            <div
                className="progress-panel"
                style={{
                    flex: '1',
                    minWidth: '300px',
                    backgroundColor: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '0.5rem',
                    padding: '1rem',
                    overflowY: 'auto'
                }}
            >
                <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.125rem', fontWeight: '600' }}>
                    Agent Progress
                </h3>

                {agentProgress.length === 0 ? (
                    <div style={{ color: '#64748b', fontStyle: 'italic' }}>
                        No active agent processing
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {agentProgress.slice().reverse().map((progressEntry) => (
                            <div
                                key={progressEntry.id}
                                style={{
                                    backgroundColor: 'white',
                                    border: '1px solid #e2e8f0',
                                    borderRadius: '0.375rem',
                                    padding: '0.75rem'
                                }}
                            >
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    marginBottom: '0.5rem'
                                }}>
                                    <div style={{
                                        fontWeight: '600',
                                        textTransform: 'capitalize',
                                        color: '#1f2937'
                                    }}>
                                        {progressEntry.agentType.replace('_', ' ')}
                                    </div>
                                    <div style={{
                                        fontSize: '0.75rem',
                                        color: '#10b981',
                                        backgroundColor: '#dcfce7',
                                        padding: '0.125rem 0.5rem',
                                        borderRadius: '0.25rem'
                                    }}>
                                        {progressEntry.data.status || 'Processing'}
                                    </div>
                                </div>

                                {/* Supervisor-specific content */}
                                {progressEntry.agentType === 'supervisor' && progressEntry.data.intent_info && (
                                    <div style={{ marginBottom: '0.5rem' }}>
                                        <div style={{ fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.25rem' }}>
                                            Intent Analysis:
                                        </div>
                                        <div style={{
                                            fontSize: '0.75rem',
                                            color: '#64748b',
                                            marginBottom: '0.25rem',
                                            paddingLeft: '0.5rem',
                                            borderLeft: '2px solid #3b82f6'
                                        }}>
                                            <div><strong>Primary Intent:</strong> {progressEntry.data.intent_info.primary_intent}</div>
                                            <div><strong>Selected Agents:</strong> {progressEntry.data.selected_agents?.join(', ') || 'None'}</div>
                                        </div>
                                        {progressEntry.data.intent_info.reasoning && (
                                            <div style={{
                                                fontSize: '0.75rem',
                                                color: '#374151',
                                                marginTop: '0.5rem',
                                                padding: '0.5rem',
                                                backgroundColor: '#f9fafb',
                                                borderRadius: '0.25rem',
                                                border: '1px solid #e5e7eb'
                                            }}>
                                                <strong>Reasoning:</strong> {progressEntry.data.intent_info.reasoning}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Regular agent responses */}
                                {progressEntry.data.agent_responses && Object.keys(progressEntry.data.agent_responses).length > 0 && (
                                    <div style={{ marginBottom: '0.5rem' }}>
                                        <div style={{ fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.25rem' }}>
                                            Agent Responses:
                                        </div>
                                        {Object.entries(progressEntry.data.agent_responses).map(([responseAgent, responseData]: [string, any]) => (
                                            <div key={responseAgent} style={{
                                                fontSize: '0.75rem',
                                                color: '#64748b',
                                                marginBottom: '0.25rem',
                                                paddingLeft: '0.5rem',
                                                borderLeft: '2px solid #e2e8f0'
                                            }}>
                                                <strong>{responseAgent}:</strong> {responseData.response?.substring(0, 100)}...
                                            </div>
                                        ))}
                                    </div>
                                )}



                                {progressEntry.timestamp && (
                                    <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
                                        {new Date(progressEntry.timestamp).toLocaleTimeString()}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default WebSocketChatInterface;