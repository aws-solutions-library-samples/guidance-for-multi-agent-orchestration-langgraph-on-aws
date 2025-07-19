import { useChat } from '@ai-sdk/react';
import { useCallback, useEffect, useState } from 'react';
import { useAuth } from './useAuth';
import { useSendChat, useCreateSession, useChatHistory } from './useGraphQL';
import type { ChatMessage, SendChatInput } from '../types';

interface AIMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt?: Date;
}

interface UseAIChatOptions {
  sessionId?: string;
  initialMessages?: AIMessage[];
  onFinish?: (message: AIMessage) => void;
  onError?: (error: Error) => void;
}

export function useAIChat(options: UseAIChatOptions = {}) {
  const { user } = useAuth();
  const { sendMessage: sendGraphQLMessage, loading: sendingMessage } = useSendChat();
  const { createSession, loading: creatingSession } = useCreateSession();
  const { messages: graphqlMessages, loading: loadingHistory } = useChatHistory(
    options.sessionId || '',
    50
  );

  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(options.sessionId);
  const [isInitialized, setIsInitialized] = useState(false);

  // Convert GraphQL messages to AI SDK format
  const convertToAIMessages = useCallback((messages: ChatMessage[]): AIMessage[] => {
    return messages.map(msg => ({
      id: msg.id,
      role: msg.sender === 'user' ? 'user' as const : 'assistant' as const,
      content: msg.content,
      createdAt: new Date(msg.timestamp)
    }));
  }, []);

  // Convert AI SDK message to GraphQL format
  const convertToGraphQLInput = useCallback((
    message: string,
    sessionId: string
  ): SendChatInput => ({
    sessionId,
    content: message,
    sender: 'user',
  }), []);

  // Custom message handler that integrates with GraphQL
  const handleSendMessage = useCallback(async (message: string) => {
    if (!user?.userId) {
      throw new Error('User not authenticated');
    }

    let sessionId = currentSessionId;

    // Create session if none exists
    if (!sessionId) {
      try {
        const sessionResult = await createSession({
          userId: user.userId,
        });

        if (sessionResult?.success && sessionResult.session) {
          sessionId = sessionResult.session.sessionId;
          setCurrentSessionId(sessionId);
        } else {
          throw new Error('Failed to create chat session');
        }
      } catch (error) {
        console.error('Error creating session:', error);
        throw error;
      }
    }

    // Send message via GraphQL
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
  }, [user?.userId, currentSessionId, createSession, sendGraphQLMessage, convertToGraphQLInput]);

  // Initialize AI SDK chat with custom adapter
  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    error,
    reload,
    stop,
    append,
    setMessages,
    setInput
  } = useChat({
    api: '/api/chat', // This will be intercepted by our custom handler
    initialMessages: options.initialMessages,
    onFinish: options.onFinish,
    onError: options.onError,
    // Custom message handler
    body: {
      sessionId: currentSessionId
    }
  });

  // Override the default submit handler to use GraphQL
  const customHandleSubmit = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();

    if (!input.trim() || isLoading) return;

    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      createdAt: new Date()
    };

    // Add user message immediately for optimistic UI
    setMessages(prev => [...prev, userMessage]);
    setInput('');

    try {
      const result = await handleSendMessage(input);

      if (result?.agentResponse) {
        const assistantMessage: AIMessage = {
          id: result.id + '_response',
          role: 'assistant',
          content: result.agentResponse.content,
          createdAt: new Date(result.agentResponse.timestamp)
        };

        setMessages(prev => [...prev, assistantMessage]);
        options.onFinish?.(assistantMessage);
      }
    } catch (error) {
      console.error('Error in custom submit:', error);
      options.onError?.(error as Error);

      // Remove optimistic user message on error
      setMessages(prev => prev.filter(msg => msg.id !== userMessage.id));
      setInput(input); // Restore input
    }
  }, [input, isLoading, handleSendMessage, setMessages, setInput, options]);

  // Load existing messages when session changes
  useEffect(() => {
    if (currentSessionId && graphqlMessages.length > 0 && !isInitialized) {
      const aiMessages = convertToAIMessages(graphqlMessages);
      setMessages(aiMessages);
      setIsInitialized(true);
    }
  }, [currentSessionId, graphqlMessages, convertToAIMessages, setMessages, isInitialized]);

  // Reset initialization when session changes
  useEffect(() => {
    setIsInitialized(false);
  }, [currentSessionId]);

  return {
    // AI SDK interface
    messages,
    input,
    handleInputChange,
    handleSubmit: customHandleSubmit,
    isLoading: isLoading || sendingMessage || creatingSession,
    error,
    reload,
    stop,
    append,
    setMessages,
    setInput,

    // Additional GraphQL-specific functionality
    sessionId: currentSessionId,
    setSessionId: setCurrentSessionId,
    loadingHistory,

    // Helper methods
    createNewSession: useCallback(async () => {
      if (!user?.userId) return;

      const result = await createSession({
        userId: user.userId,
      });

      if (result?.success && result.session) {
        setCurrentSessionId(result.session.sessionId);
        setMessages([]);
        setIsInitialized(false);
        return result.session.sessionId;
      }
    }, [user?.userId, createSession, setMessages]),

    clearMessages: useCallback(() => {
      setMessages([]);
    }, [setMessages])
  };
}

// Hook for streaming chat with real-time updates
export function useStreamingAIChat(sessionId: string, options: UseAIChatOptions = {}) {
  const baseChat = useAIChat({ ...options, sessionId });
  const [streamingMessage, setStreamingMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);

  // Simulate streaming for agent responses
  const simulateStreaming = useCallback((content: string, onComplete?: () => void) => {
    setIsStreaming(true);
    setStreamingMessage('');

    let index = 0;
    const interval = setInterval(() => {
      if (index < content.length) {
        setStreamingMessage(prev => prev + content[index]);
        index++;
      } else {
        clearInterval(interval);
        setIsStreaming(false);
        setStreamingMessage('');
        onComplete?.();
      }
    }, 50); // Adjust speed as needed

    return () => clearInterval(interval);
  }, []);

  return {
    ...baseChat,
    streamingMessage,
    isStreaming,
    simulateStreaming
  };
}