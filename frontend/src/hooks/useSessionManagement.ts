import { useState, useCallback } from 'react';
import { useAuth } from './useAuth';
import { useCreateSession } from './useAmplifyGraphQL';

interface UseSessionManagementReturn {
  sessionId: string | null;
  createNewSession: () => Promise<string>;
  isCreating: boolean;
  error: Error | null;
}

export const useSessionManagement = (
  initialSessionId?: string
): UseSessionManagementReturn => {
  const { user } = useAuth();
  const { createSession, loading: creatingSession } = useCreateSession();
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null);
  const [error, setError] = useState<Error | null>(null);

  // Create new session - extracted from useAIAmplifyChat
  const createNewSession = useCallback(async (): Promise<string> => {
    if (!user?.userId) {
      throw new Error('User not authenticated');
    }

    setError(null);

    try {
      const result = await createSession({
        userId: user.userId,
      });

      if (result?.success && result.session) {
        setSessionId(result.session.sessionId);
        return result.session.sessionId;
      } else {
        throw new Error(result?.error || 'Failed to create chat session');
      }
    } catch (err) {
      const error = err as Error;
      setError(error);
      throw error;
    }
  }, [user?.userId, createSession]);

  return {
    sessionId,
    createNewSession,
    isCreating: creatingSession,
    error
  };
};