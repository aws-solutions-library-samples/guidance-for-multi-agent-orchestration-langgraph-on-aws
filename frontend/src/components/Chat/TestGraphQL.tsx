import React, { useState, useRef } from 'react';
import { useHealthCheck, useCreateSession, useSendChat } from '../../hooks/useAmplifyGraphQL';
import { generateClient } from 'aws-amplify/api';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';

// Initialize Amplify GraphQL client for streaming
const client = generateClient();

const TestGraphQL: React.FC = () => {
  const [userId, setUserId] = useState('test-user-123');
  const [sessionId, setSessionId] = useState('');
  const [message, setMessage] = useState('I need help with my order ORD-2024-001 for customer cust001');
  const [results, setResults] = useState<any[]>([]);
  const [streamingResults, setStreamingResults] = useState<any[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamingAbortController = useRef<AbortController | null>(null);

  const { isHealthy, loading: healthLoading, refetch: checkHealth } = useHealthCheck();
  const { createSession, loading: createLoading } = useCreateSession();
  const { sendMessage, loading: sendLoading } = useSendChat();

  const addResult = (operation: string, result: any) => {
    setResults(prev => [...prev, {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      operation,
      result: JSON.stringify(result, null, 2)
    }]);
  };

  const addStreamingResult = (type: string, data: any) => {
    setStreamingResults(prev => [...prev, {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      type,
      data: JSON.stringify(data, null, 2)
    }]);
  };

  const handleHealthCheck = async () => {
    try {
      await checkHealth();
      addResult('Health Check', { isHealthy, status: 'completed' });
    } catch (error) {
      addResult('Health Check', { error: error.message });
    }
  };

  const handleCreateSession = async () => {
    try {
      const result = await createSession({
        userId,
      });

      if (result?.success && result.session) {
        setSessionId(result.session.sessionId);
        addResult('Create Session', result);
      } else {
        addResult('Create Session', { error: result?.error || 'Unknown error' });
      }
    } catch (error) {
      addResult('Create Session', { error: error.message });
    }
  };

  const handleSendMessage = async () => {
    if (!sessionId) {
      addResult('Send Message', { error: 'No session ID available' });
      return;
    }

    try {
      const result = await sendMessage({
        sessionId,
        message,

      });

      addResult('Send Message', result);
    } catch (error) {
      addResult('Send Message', { error: error.message });
    }
  };

  const handleStreamingChat = async () => {
    if (!sessionId) {
      addStreamingResult('Error', { error: 'No session ID available' });
      return;
    }

    setIsStreaming(true);
    setStreamingResults([]);
    streamingAbortController.current = new AbortController();

    const streamingQuery = `
      mutation SendChatStream($input: SendChatInput!) {
        sendChat(input: $input) {
          success
          error
          message {
            agentResponse {
              
              content
            }
            
          }
          
        }
      }
    `;

    try {
      addStreamingResult('Stream Started', {
        sessionId,
        message,
        timestamp: new Date().toISOString()
      });

      // Use GraphQL subscription or streaming mutation
      const response = await client.graphql({
        query: streamingQuery,
        variables: {
          input: {
            sessionId,
            message,

          }
        }
      });

      addStreamingResult('Stream Response', response.data);

      // If the backend supports real streaming, we might need to handle it differently
      // For now, this will work with the regular mutation response

    } catch (error) {
      addStreamingResult('Stream Error', {
        error: error.message,
        details: error
      });
    } finally {
      setIsStreaming(false);
      streamingAbortController.current = null;
    }
  };

  const handleStreamingSubscription = async () => {
    if (!sessionId) {
      addStreamingResult('Error', { error: 'No session ID available' });
      return;
    }

    setIsStreaming(true);
    setStreamingResults([]);

    const subscriptionQuery = `
      subscription OnChatMessage($sessionId: ID!) {
        onChatMessage(sessionId: $sessionId) {
          success
          message {
            id
            content
            sender
            timestamp
            agentResponse {
              agentType
              content
              confidence
              processingTime
              metadata
              timestamp
            }
            metadata
          }
          error
        }
      }
    `;

    try {
      addStreamingResult('Subscription Started', {
        sessionId,
        timestamp: new Date().toISOString()
      });

      const subscription = client.graphql({
        query: subscriptionQuery,
        variables: { sessionId }
      }).subscribe({
        next: ({ data }) => {
          addStreamingResult('Subscription Update', data);
        },
        error: (error) => {
          addStreamingResult('Subscription Error', {
            error: error.message,
            details: error
          });
          setIsStreaming(false);
        }
      });

      // Auto-unsubscribe after 30 seconds for testing
      setTimeout(() => {
        subscription.unsubscribe();
        addStreamingResult('Subscription Ended', {
          reason: 'timeout',
          timestamp: new Date().toISOString()
        });
        setIsStreaming(false);
      }, 30000);

    } catch (error) {
      addStreamingResult('Subscription Setup Error', {
        error: error.message,
        details: error
      });
      setIsStreaming(false);
    }
  };

  const stopStreaming = () => {
    if (streamingAbortController.current) {
      streamingAbortController.current.abort();
    }
    setIsStreaming(false);
    addStreamingResult('Stream Stopped', {
      reason: 'user_cancelled',
      timestamp: new Date().toISOString()
    });
  };

  const clearResults = () => {
    setResults([]);
  };

  const clearStreamingResults = () => {
    setStreamingResults([]);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>GraphQL API Test Interface</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Health Check */}
          <div className="flex items-center gap-4">
            <Button
              onClick={handleHealthCheck}
              disabled={healthLoading}
              variant="outline"
            >
              {healthLoading ? 'Checking...' : 'Health Check'}
            </Button>
            <Badge variant={isHealthy ? 'success' : 'destructive'}>
              {isHealthy ? 'Healthy' : 'Unhealthy'}
            </Badge>
          </div>

          {/* Create Session */}
          <div className="space-y-2">
            <div className="flex items-center gap-4">
              <Input
                placeholder="User ID"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="max-w-xs"
              />
              <Button
                onClick={handleCreateSession}
                disabled={createLoading || !userId}
                variant="outline"
              >
                {createLoading ? 'Creating...' : 'Create Session'}
              </Button>
            </div>
            {sessionId && (
              <p className="text-sm text-muted-foreground">
                Session ID: {sessionId}
              </p>
            )}
          </div>

          {/* Send Message */}
          <div className="space-y-2">
            <div className="flex items-center gap-4">
              <Input
                placeholder="Message to send"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="flex-1"
              />
              <Button
                onClick={handleSendMessage}
                disabled={sendLoading || !sessionId || !message}
              >
                {sendLoading ? 'Sending...' : 'Send Message'}
              </Button>
            </div>
          </div>

          {/* Streaming Tests */}
          <div className="border-t pt-4">
            <h3 className="text-lg font-semibold mb-4">Streaming API Tests</h3>
            <div className="flex flex-wrap gap-4">
              <Button
                onClick={handleStreamingChat}
                disabled={isStreaming || !sessionId || !message}
                variant="secondary"
              >
                {isStreaming ? 'Streaming...' : 'Test Streaming Chat'}
              </Button>

              <Button
                onClick={handleStreamingSubscription}
                disabled={isStreaming || !sessionId}
                variant="secondary"
              >
                {isStreaming ? 'Listening...' : 'Test Subscription'}
              </Button>

              {isStreaming && (
                <Button
                  onClick={stopStreaming}
                  variant="destructive"
                  size="sm"
                >
                  Stop Streaming
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Regular Results */}
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Regular API Results</h3>
            <Button onClick={clearResults} variant="outline" size="sm">
              Clear Results
            </Button>
          </div>

          <div className="space-y-4 max-h-96 overflow-y-auto">
            {results.map((result) => (
              <Card key={result.id}>
                <CardHeader className="pb-2">
                  <div className="flex justify-between items-center">
                    <CardTitle className="text-sm">{result.operation}</CardTitle>
                    <span className="text-xs text-muted-foreground">
                      {new Date(result.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-32">
                    {result.result}
                  </pre>
                </CardContent>
              </Card>
            ))}

            {results.length === 0 && (
              <Card>
                <CardContent className="text-center py-8 text-muted-foreground">
                  No regular API results yet.
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* Streaming Results */}
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Streaming API Results</h3>
            <div className="flex gap-2">
              {isStreaming && (
                <Badge variant="secondary" className="animate-pulse">
                  Streaming Active
                </Badge>
              )}
              <Button onClick={clearStreamingResults} variant="outline" size="sm">
                Clear Results
              </Button>
            </div>
          </div>

          <div className="space-y-4 max-h-96 overflow-y-auto">
            {streamingResults.map((result) => (
              <Card key={result.id}>
                <CardHeader className="pb-2">
                  <div className="flex justify-between items-center">
                    <CardTitle className="text-sm flex items-center gap-2">
                      {result.type}
                      <Badge variant="outline" className="text-2xs">
                        Stream
                      </Badge>
                    </CardTitle>
                    <span className="text-xs text-muted-foreground">
                      {new Date(result.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-32">
                    {result.data}
                  </pre>
                </CardContent>
              </Card>
            ))}

            {streamingResults.length === 0 && (
              <Card>
                <CardContent className="text-center py-8 text-muted-foreground">
                  No streaming results yet. Try the streaming tests above.
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TestGraphQL;
