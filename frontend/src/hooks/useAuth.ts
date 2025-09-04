import { useAuthenticator } from '@aws-amplify/ui-react';
import { useEffect, useState } from 'react';

export interface UseAuthReturn {
  user: any | null; // Using any since AuthUser type is not properly exported
  isAuthenticated: boolean;
  isLoading: boolean;
  signOut: () => void;
  error: string | null;
}

/**
 * Custom hook for authentication state management using Amplify's built-in hooks
 * Provides a clean interface for authentication state and actions
 */
export function useAuth(): UseAuthReturn {
  const { user, signOut: amplifySignOut, authStatus } = useAuthenticator();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Determine authentication state based on authStatus
  const isAuthenticated = authStatus === 'authenticated';

  // Handle loading state
  useEffect(() => {
    if (authStatus === 'configuring') {
      setIsLoading(true);
    } else {
      setIsLoading(false);
    }
  }, [authStatus]);

  // Clear error when authentication status changes
  useEffect(() => {
    if (isAuthenticated) {
      setError(null);
    }
  }, [isAuthenticated]);

  // Enhanced sign out function with error handling
  const handleSignOut = async () => {
    try {
      setError(null);
      await amplifySignOut();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to sign out';
      setError(errorMessage);
      console.error('Sign out error:', err);
    }
  };

  return {
    user: user || null,
    isAuthenticated,
    isLoading,
    signOut: handleSignOut,
    error,
  };
}

/**
 * Hook to get user attributes in a type-safe way
 */
export function useUserAttributes() {
  const { user } = useAuth();

  return {
    email: user?.signInDetails?.loginId || '',
    username: user?.username || '',
    userId: user?.userId || '',
    attributes: user?.signInDetails || {},
  };
}