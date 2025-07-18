import { useQuery, useMutation, useSubscription, QueryResult, MutationResult } from '@apollo/client';
import { useCallback, useEffect, useState } from 'react';
import type {
  ChatMessage,
  ChatSession,
  AgentStatus,
  TaskResult,
  SendChatInput,
  CreateSessionInput,
  ExecuteTaskInput,
  AgentType
} from '../types';
import {
  GET_SESSION,
  GET_USER_SESSIONS,
  GET_CHAT_HISTORY,
  GET_ALL_AGENT_STATUSES,
  GET_AGENTS_BY_TYPE,
  HEALTH_CHECK,
  SEND_CHAT,
  CREATE_SESSION,
  CLOSE_SESSION,
  EXECUTE_TASK_ON_AGENT,
  ON_CHAT_MESSAGE,
  ON_AGENT_STATUS_CHANGE
} from '../graphql/operations';

// Custom hook for session management
export function useSession(sessionId?: string) {
  const { data, loading, error, refetch } = useQuery(GET_SESSION, {
    variables: { sessionId },
    skip: !sessionId,
    errorPolicy: 'all'
  });

  return {
    session: data?.getSession,
    loading,
    error,
    refetch
  };
}

// Custom hook for user sessions
export function useUserSessions(userId: string, limit = 20) {
  const { data, loading, error, refetch, fetchMore } = useQuery(GET_USER_SESSIONS, {
    variables: { userId, limit },
    skip: !userId,
    errorPolicy: 'all'
  });

  const loadMore = useCallback(async (nextToken?: string) => {
    if (!nextToken) return;
    
    try {
      await fetchMore({
        variables: { userId, limit, nextToken },
        updateQuery: (prev, { fetchMoreResult }) => {
          if (!fetchMoreResult) return prev;
          return {
            getUserSessions: [
              ...prev.getUserSessions,
              ...fetchMoreResult.getUserSessions
            ]
          };
        }
      });
    } catch (err) {
      console.error('Error loading more sessions:', err);
    }
  }, [fetchMore, userId, limit]);

  return {
    sessions: data?.getUserSessions || [],
    loading,
    error,
    refetch,
    loadMore
  };
}

// Custom hook for chat history
export function useChatHistory(sessionId: string, limit = 50) {
  const { data, loading, error, refetch, fetchMore } = useQuery(GET_CHAT_HISTORY, {
    variables: { sessionId, limit },
    skip: !sessionId,
    errorPolicy: 'all'
  });

  const loadMore = useCallback(async (nextToken?: string) => {
    if (!nextToken) return;
    
    try {
      await fetchMore({
        variables: { sessionId, limit, nextToken },
        updateQuery: (prev, { fetchMoreResult }) => {
          if (!fetchMoreResult) return prev;
          return {
            getChatHistory: [
              ...fetchMoreResult.getChatHistory,
              ...prev.getChatHistory
            ]
          };
        }
      });
    } catch (err) {
      console.error('Error loading more chat history:', err);
    }
  }, [fetchMore, sessionId, limit]);

  return {
    messages: data?.getChatHistory || [],
    loading,
    error,
    refetch,
    loadMore
  };
}

// Custom hook for agent statuses
export function useAgentStatuses(agentType?: AgentType) {
  const { data, loading, error, refetch } = useQuery(
    agentType ? GET_AGENTS_BY_TYPE : GET_ALL_AGENT_STATUSES,
    {
      variables: agentType ? { agentType } : undefined,
      errorPolicy: 'all',
      pollInterval: 30000 // Poll every 30 seconds for status updates
    }
  );

  return {
    agents: agentType ? data?.getAgentsByType || [] : data?.getAllAgentStatuses || [],
    loading,
    error,
    refetch
  };
}

// Custom hook for health check
export function useHealthCheck() {
  const { data, loading, error, refetch } = useQuery(HEALTH_CHECK, {
    errorPolicy: 'all',
    pollInterval: 60000 // Poll every minute
  });

  return {
    isHealthy: data?.healthCheck === 'OK',
    loading,
    error,
    refetch
  };
}

// Custom hook for sending chat messages
export function useSendChat() {
  const [sendChatMutation, { loading, error }] = useMutation(SEND_CHAT, {
    errorPolicy: 'all'
  });

  const sendMessage = useCallback(async (input: SendChatInput) => {
    try {
      const result = await sendChatMutation({
        variables: { input },
        update: (cache, { data }) => {
          if (data?.sendChat?.success && data.sendChat.message) {
            // Update chat history cache
            const existingHistory = cache.readQuery({
              query: GET_CHAT_HISTORY,
              variables: { sessionId: input.sessionId }
            });

            if (existingHistory) {
              cache.writeQuery({
                query: GET_CHAT_HISTORY,
                variables: { sessionId: input.sessionId },
                data: {
                  getChatHistory: [
                    ...existingHistory.getChatHistory,
                    data.sendChat.message
                  ]
                }
              });
            }
          }
        }
      });

      return result.data?.sendChat;
    } catch (err) {
      console.error('Error sending chat message:', err);
      throw err;
    }
  }, [sendChatMutation]);

  return {
    sendMessage,
    loading,
    error
  };
}

// Custom hook for creating sessions
export function useCreateSession() {
  const [createSessionMutation, { loading, error }] = useMutation(CREATE_SESSION, {
    errorPolicy: 'all'
  });

  const createSession = useCallback(async (input: CreateSessionInput) => {
    try {
      const result = await createSessionMutation({
        variables: { input },
        update: (cache, { data }) => {
          if (data?.createSession?.success && data.createSession.session) {
            // Update user sessions cache
            const existingSessions = cache.readQuery({
              query: GET_USER_SESSIONS,
              variables: { userId: input.userId }
            });

            if (existingSessions) {
              cache.writeQuery({
                query: GET_USER_SESSIONS,
                variables: { userId: input.userId },
                data: {
                  getUserSessions: [
                    data.createSession.session,
                    ...existingSessions.getUserSessions
                  ]
                }
              });
            }
          }
        }
      });

      return result.data?.createSession;
    } catch (err) {
      console.error('Error creating session:', err);
      throw err;
    }
  }, [createSessionMutation]);

  return {
    createSession,
    loading,
    error
  };
}

// Custom hook for closing sessions
export function useCloseSession() {
  const [closeSessionMutation, { loading, error }] = useMutation(CLOSE_SESSION, {
    errorPolicy: 'all'
  });

  const closeSession = useCallback(async (sessionId: string) => {
    try {
      const result = await closeSessionMutation({
        variables: { sessionId },
        update: (cache, { data }) => {
          if (data?.closeSession?.success && data.closeSession.session) {
            // Update session cache
            cache.writeQuery({
              query: GET_SESSION,
              variables: { sessionId },
              data: {
                getSession: data.closeSession.session
              }
            });
          }
        }
      });

      return result.data?.closeSession;
    } catch (err) {
      console.error('Error closing session:', err);
      throw err;
    }
  }, [closeSessionMutation]);

  return {
    closeSession,
    loading,
    error
  };
}

// Custom hook for executing tasks on agents
export function useExecuteTask() {
  const [executeTaskMutation, { loading, error }] = useMutation(EXECUTE_TASK_ON_AGENT, {
    errorPolicy: 'all'
  });

  const executeTask = useCallback(async (input: ExecuteTaskInput) => {
    try {
      const result = await executeTaskMutation({
        variables: { input }
      });

      return result.data?.executeTaskOnAgent;
    } catch (err) {
      console.error('Error executing task:', err);
      throw err;
    }
  }, [executeTaskMutation]);

  return {
    executeTask,
    loading,
    error
  };
}

// Custom hook for GraphQL subscriptions with connection management
export function useGraphQLSubscription<T>(
  subscription: any,
  variables?: any,
  options?: {
    onData?: (data: T) => void;
    onError?: (error: Error) => void;
    skip?: boolean;
  }
) {
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastData, setLastData] = useState<T | null>(null);

  const { data, loading, error } = useSubscription(subscription, {
    variables,
    skip: options?.skip,
    onData: ({ data }) => {
      setConnectionStatus('connected');
      setLastData(data);
      options?.onData?.(data);
    },
    onError: (error) => {
      setConnectionStatus('error');
      options?.onError?.(error);
      console.error('Subscription error:', error);
    }
  });

  useEffect(() => {
    if (loading) {
      setConnectionStatus('connecting');
    } else if (error) {
      setConnectionStatus('error');
    } else if (data) {
      setConnectionStatus('connected');
    }
  }, [loading, error, data]);

  return {
    data: lastData,
    loading,
    error,
    connectionStatus
  };
}

// Custom hook for chat message subscriptions
export function useChatMessageSubscription(sessionId: string, enabled = true) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const { data, loading, error, connectionStatus } = useGraphQLSubscription(
    ON_CHAT_MESSAGE,
    { sessionId },
    {
      skip: !enabled || !sessionId,
      onData: (data: any) => {
        if (data?.onChatMessage?.success && data.onChatMessage.message) {
          setMessages(prev => [...prev, data.onChatMessage.message]);
        }
      },
      onError: (error) => {
        console.error('Chat message subscription error:', error);
      }
    }
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    loading,
    error,
    connectionStatus,
    clearMessages
  };
}

// Custom hook for agent status subscriptions
export function useAgentStatusSubscription(enabled = true) {
  const [statusUpdates, setStatusUpdates] = useState<AgentStatus[]>([]);

  const { data, loading, error, connectionStatus } = useGraphQLSubscription(
    ON_AGENT_STATUS_CHANGE,
    {},
    {
      skip: !enabled,
      onData: (data: any) => {
        if (data?.onAgentStatusChange) {
          setStatusUpdates(prev => {
            const existing = prev.find(s => s.agentId === data.onAgentStatusChange.agentId);
            if (existing) {
              return prev.map(s => 
                s.agentId === data.onAgentStatusChange.agentId 
                  ? data.onAgentStatusChange 
                  : s
              );
            }
            return [...prev, data.onAgentStatusChange];
          });
        }
      },
      onError: (error) => {
        console.error('Agent status subscription error:', error);
      }
    }
  );

  const clearStatusUpdates = useCallback(() => {
    setStatusUpdates([]);
  }, []);

  return {
    statusUpdates,
    loading,
    error,
    connectionStatus,
    clearStatusUpdates
  };
}

// Custom hook for connection monitoring and automatic reconnection
export function useConnectionMonitor() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [lastReconnectTime, setLastReconnectTime] = useState<Date | null>(null);

  const { isHealthy, refetch: checkHealth } = useHealthCheck();

  // Monitor online/offline status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Automatic reconnection logic with exponential backoff
  const reconnect = useCallback(async () => {
    if (!isOnline) return false;

    try {
      setReconnectAttempts(prev => prev + 1);
      await checkHealth();
      setLastReconnectTime(new Date());
      return true;
    } catch (error) {
      console.error('Reconnection failed:', error);
      
      // Exponential backoff: wait longer between attempts
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
      setTimeout(() => {
        if (reconnectAttempts < 5) {
          reconnect();
        }
      }, delay);
      
      return false;
    }
  }, [isOnline, checkHealth, reconnectAttempts]);

  // Reset reconnect attempts on successful connection
  useEffect(() => {
    if (isHealthy && isOnline) {
      setReconnectAttempts(0);
    }
  }, [isHealthy, isOnline]);

  // Auto-reconnect when coming back online
  useEffect(() => {
    if (isOnline && !isHealthy && reconnectAttempts === 0) {
      reconnect();
    }
  }, [isOnline, isHealthy, reconnectAttempts, reconnect]);

  return {
    isOnline,
    isHealthy,
    reconnectAttempts,
    lastReconnectTime,
    reconnect
  };
}

// Error handling hook for GraphQL operations
export function useGraphQLError() {
  const [errors, setErrors] = useState<Array<{ id: string; message: string; timestamp: Date }>>([]);

  const addError = useCallback((error: Error | string) => {
    const errorMessage = typeof error === 'string' ? error : error.message;
    const newError = {
      id: Date.now().toString(),
      message: errorMessage,
      timestamp: new Date()
    };
    
    setErrors(prev => [...prev, newError]);
    
    // Auto-remove error after 10 seconds
    setTimeout(() => {
      setErrors(prev => prev.filter(e => e.id !== newError.id));
    }, 10000);
  }, []);

  const removeError = useCallback((id: string) => {
    setErrors(prev => prev.filter(e => e.id !== id));
  }, []);

  const clearErrors = useCallback(() => {
    setErrors([]);
  }, []);

  return {
    errors,
    addError,
    removeError,
    clearErrors
  };
}