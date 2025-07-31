import { useCallback, useEffect, useState } from 'react';
import { useAuth } from './useAuth';
import {
  useSendChat,
  useCreateSession,
  useChatHistory,
  useChatMessageSubscription
} from './useAmplifyGraphQL';
import type { ChatMessage, SendChatInput, AgentType } from '../types';

interface AIMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt?: Date;
  agentType?: AgentType;
  confidence?: number;
  processingTime?: number;
  metadata?: Record<string, any>;
}

interface UseAIAmplifyChat {
  sessionId?: string;
  initialMessages?: AIMessage[];
  onFinish?: (message: AIMessage) => void;
  onError?: (error: Error) => void;
  onAgentResponse?: (agentType: AgentType, message: AIMessage) => void;
}

export function useAIAmplifyChat(options: UseAIAmplifyChat = {}) {
  const { user } = useAuth();
  const { sendMessage: sendGraphQLMessage, loading: sendingMessage } = useSendChat();
  const { createSession, loading: creatingSession } = useCreateSession();
  const { messages: graphqlMessages, loading: loadingHistory } = useChatHistory(
    options.sessionId || '',
    50
  );

  // State management
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(options.sessionId);
  const [messages, setMessages] = useState<AIMessage[]>(options.initialMessages || []);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Real-time message subscription
  // Real-time message subscription - ONLY WHEN ACTIVELY CHATTING
  const {
    messages: subscriptionMessages,
    connectionStatus
  } = useChatMessageSubscription(
    currentSessionId || '',
    !!currentSessionId && messages.length > 0 // Only enable after first message is sent
  );

  // Convert GraphQL messages to AI SDK format
  const convertToAIMessages = useCallback((messages: ChatMessage[]): AIMessage[] => {
    return messages.map(msg => ({
      id: msg.id,
      role: msg.sender === 'USER' ? 'user' as const : 'assistant' as const,
      content: msg.content,
      createdAt: new Date(msg.timestamp),
      agentType: msg.agentResponse?.agentType,
      confidence: msg.agentResponse?.confidence,
      processingTime: msg.agentResponse?.processingTime,
      metadata: msg.metadata
    }));
  }, []);

  // Convert AI SDK message to GraphQL format
  const convertToGraphQLInput = useCallback((
    message: string,
    sessionId: string
  ): SendChatInput => ({
    sessionId,
    message,
  }), []);

  // Handle input change - auto-create session if needed
  // Handle input change
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value);
  }, []);

  // Create new session
  const createNewSession = useCallback(async () => {
    if (!user?.userId) {
      throw new Error('User not authenticated');
    }

    try {
      const result = await createSession({
        userId: user.userId,
      });

      if (result?.success && result.session) {
        setCurrentSessionId(result.session.sessionId);
        setMessages([]);
        setIsInitialized(false);
        return result.session.sessionId;
      } else {
        throw new Error(result?.error || 'Failed to create chat session');
      }
    } catch (error) {
      console.error('Error creating session:', error);
      throw error;
    }
  }, [user?.userId, createSession]);

  // Send message
  const sendMessage = useCallback(async (message: string) => {
    if (!user?.userId) {
      throw new Error('User not authenticated');
    }

    let sessionId = currentSessionId;

    // Create session if none exists
    if (!sessionId) {
      sessionId = await createNewSession();
    }

    if (!sessionId) {
      throw new Error('Failed to create or get session');
    }

    try {
      const input = convertToGraphQLInput(message, sessionId);
      const result = await sendGraphQLMessage(input);

      if (!result?.success) {
        throw new Error(result?.error || 'Failed to send message');
      }

      return result.message;
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }, [user?.userId, currentSessionId, createNewSession, sendGraphQLMessage, convertToGraphQLInput]);

  // Handle form submission
  const handleSubmit = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();

    if (!input.trim() || isLoading) return;

    // Store the input value before clearing it
    const inputValue = input.trim();

    const userMessage: AIMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: inputValue,
      createdAt: new Date()
    };

    // Add user message immediately for optimistic UI
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      const result = await sendMessage(inputValue);

      // Remove temporary message and add real ones
      setMessages(prev => prev.filter(msg => msg.id !== userMessage.id));

      if (result) {
        // Add user message from backend response
        const realUserMessage: AIMessage = {
          id: result.id,
          role: 'user',
          content: result.content,
          createdAt: new Date(result.timestamp)
        };

        setMessages(prev => [...prev, realUserMessage]);

        // Add agent response if available
        if (result.agentResponse) {
          const assistantMessage: AIMessage = {
            id: result.agentResponse.id || `${result.id}_response`,
            role: 'assistant',
            content: result.agentResponse.content,
            createdAt: new Date(result.agentResponse.timestamp),
            agentType: result.agentResponse.agentType,
            confidence: result.agentResponse.confidence,
            processingTime: result.agentResponse.processingTime,
            metadata: result.agentResponse.metadata
          };

          setMessages(prev => [...prev, assistantMessage]);
          options.onFinish?.(assistantMessage);
          options.onAgentResponse?.(result.agentResponse.agentType, assistantMessage);
        }
      }
    } catch (error) {
      console.error('Error in submit:', error);
      setError(error as Error);
      options.onError?.(error as Error);

      // Remove optimistic user message on error
      setMessages(prev => prev.filter(msg => msg.id !== userMessage.id));
      setInput(inputValue); // Restore input with the stored value
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, sendMessage, options]);

  // Load existing messages when session changes
  useEffect(() => {
    if (currentSessionId && graphqlMessages.length > 0 && !isInitialized) {
      const aiMessages = convertToAIMessages(graphqlMessages);
      setMessages(aiMessages);
      setIsInitialized(true);
    }
  }, [currentSessionId, graphqlMessages, convertToAIMessages, isInitialized]);

  // Handle real-time subscription messages
  useEffect(() => {
    if (subscriptionMessages.length > 0) {
      const newAIMessages = convertToAIMessages(subscriptionMessages);
      setMessages(prev => {
        // Avoid duplicates by checking if message already exists
        const existingIds = new Set(prev.map(m => m.id));
        const uniqueNewMessages = newAIMessages.filter(m => !existingIds.has(m.id));
        return [...prev, ...uniqueNewMessages];
      });
    }
  }, [subscriptionMessages, convertToAIMessages]);

  // Reset initialization when session changes
  useEffect(() => {
    setIsInitialized(false);
  }, [currentSessionId]);

  // Utility functions
  const append = useCallback(async (message: AIMessage) => {
    if (message.role === 'user') {
      await sendMessage(message.content);
    } else {
      setMessages(prev => [...prev, message]);
    }
  }, [sendMessage]);

  const reload = useCallback(async () => {
    if (messages.length > 0) {
      const lastUserMessage = [...messages].reverse().find(m => m.role === 'user');
      if (lastUserMessage) {
        await sendMessage(lastUserMessage.content);
      }
    }
  }, [messages, sendMessage]);

  const stop = useCallback(() => {
    setIsLoading(false);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    // Core AI SDK interface
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading: isLoading || sendingMessage || creatingSession,
    error,
    reload,
    stop,
    append,
    setMessages,
    setInput,

    // Additional functionality
    sessionId: currentSessionId,
    setSessionId: setCurrentSessionId,
    loadingHistory,
    connectionStatus,

    // Helper methods
    createNewSession,
    clearMessages
  };
}

// Hook for streaming chat with enhanced real-time updates - CONSERVATIVE CONNECTIONS
export function useStreamingAIAmplifyChat(sessionId: string, options: UseAIAmplifyChat = {}) {
  const baseChat = useAIAmplifyChat({ ...options, sessionId });
  const [streamingMessage, setStreamingMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingAgentType, setStreamingAgentType] = useState<AgentType | null>(null);

  // Enhanced streaming simulation with agent type awareness
  const simulateStreaming = useCallback((
    content: string,
    agentType?: AgentType,
    onComplete?: () => void
  ) => {
    setIsStreaming(true);
    setStreamingMessage('');
    setStreamingAgentType(agentType || null);

    let index = 0;
    const interval = setInterval(() => {
      if (index < content.length) {
        setStreamingMessage(prev => prev + content[index]);
        index++;
      } else {
        clearInterval(interval);
        setIsStreaming(false);
        setStreamingMessage('');
        setStreamingAgentType(null);
        onComplete?.();
      }
    }, 30); // Faster streaming for better UX

    return () => clearInterval(interval);
  }, []);

  return {
    ...baseChat,
    streamingMessage,
    isStreaming,
    streamingAgentType,
    simulateStreaming
  };
}
