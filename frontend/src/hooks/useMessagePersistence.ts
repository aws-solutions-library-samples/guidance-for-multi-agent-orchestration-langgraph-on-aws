import { useState, useCallback } from 'react';
import { useAuth } from './useAuth';
import { useChatHistory } from './useAmplifyGraphQL';
import type { ChatMessage, AgentType } from '../types';

interface ChatMessageForPersistence {
  id: string;
  sessionId: string;
  content: string;
  role: 'user' | 'assistant';
  agentType?: AgentType;
  confidence?: number;
  processingTime?: number;
  createdAt: string;
  metadata?: any;
}

interface UseMessagePersistenceReturn {
  messages: ChatMessageForPersistence[];
  saveUserMessage: (content: string, sessionId: string) => Promise<ChatMessageForPersistence>;
  saveAgentMessage: (content: string, sessionId: string, agentType: AgentType, metadata?: any) => Promise<ChatMessageForPersistence>;
  loadMessages: (sessionId: string) => Promise<void>;
  isLoading: boolean;
  error: Error | null;
}

export const useMessagePersistence = (): UseMessagePersistenceReturn => {
  const { user } = useAuth();
  const { messages: graphqlMessages, loading: loadingHistory, refetch } = useChatHistory('', 50);

  const [messages, setMessages] = useState<ChatMessageForPersistence[]>([]);
  const [error, setError] = useState<Error | null>(null);

  // Convert GraphQL messages to our format
  const convertToMessageFormat = useCallback((messages: ChatMessage[]): ChatMessageForPersistence[] => {
    return messages.map(msg => ({
      id: msg.id,
      sessionId: msg.sessionId,
      content: msg.content,
      role: msg.sender === 'USER' ? 'user' as const : 'assistant' as const,
      agentType: msg.agentResponse?.agentType,
      confidence: msg.agentResponse?.confidence,
      processingTime: msg.agentResponse?.processingTime,
      createdAt: msg.timestamp,
      metadata: msg.metadata
    }));
  }, []);

  // Save user message - for WebSocket interface, this creates a local message
  // The actual message sending is handled by the Events API
  const saveUserMessage = useCallback(async (
    content: string,
    sessionId: string
  ): Promise<ChatMessageForPersistence> => {
    if (!user?.userId) {
      throw new Error('User not authenticated');
    }

    try {
      // For WebSocket interface, we create a local message immediately
      // The supervisor agent will handle the actual persistence
      const message: ChatMessageForPersistence = {
        id: `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        sessionId,
        content,
        role: 'user',
        createdAt: new Date().toISOString(),
        metadata: {
          timestamp: new Date().toISOString(),
          source: 'WebSocketChatInterface'
        }
      };

      setMessages(prev => [...prev, message]);
      return message;
    } catch (err) {
      const error = err as Error;
      setError(error);
      throw error;
    }
  }, [user?.userId]);

  // Save agent message - creates local message for completed agent responses
  const saveAgentMessage = useCallback(async (
    content: string,
    sessionId: string,
    agentType: AgentType,
    metadata: any = {}
  ): Promise<ChatMessageForPersistence> => {
    try {
      // Create a local message for the completed agent response
      // The supervisor agent handles the actual persistence
      const message: ChatMessageForPersistence = {
        id: `agent-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        sessionId,
        content,
        role: 'assistant',
        agentType,
        confidence: metadata.confidence,
        processingTime: metadata.processingTime,
        createdAt: new Date().toISOString(),
        metadata: {
          ...metadata,
          timestamp: new Date().toISOString(),
          source: 'SupervisorAgent'
        }
      };

      setMessages(prev => [...prev, message]);
      return message;
    } catch (err) {
      const error = err as Error;
      setError(error);
      throw error;
    }
  }, []);

  // Load messages for a session
  const loadMessages = useCallback(async (sessionId: string) => {
    setError(null);

    try {
      // Use the existing GraphQL hook to fetch messages
      const result = await refetch({ sessionId, limit: 50 });
      if (result?.data?.getChatHistory?.items) {
        const convertedMessages = convertToMessageFormat(result.data.getChatHistory.items);
        setMessages(convertedMessages);
      }
    } catch (err) {
      const error = err as Error;
      setError(error);
    }
  }, [refetch, convertToMessageFormat]);

  return {
    messages,
    saveUserMessage,
    saveAgentMessage,
    loadMessages,
    isLoading: loadingHistory,
    error
  };
};