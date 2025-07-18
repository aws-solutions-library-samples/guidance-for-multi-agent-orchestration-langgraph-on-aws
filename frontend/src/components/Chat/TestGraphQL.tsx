import React, { useState } from 'react';
import { useHealthCheck, useCreateSession, useSendChat } from '../../hooks/useAmplifyGraphQL';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';

const TestGraphQL: React.FC = () => {
  const [userId, setUserId] = useState('test-user-123');
  const [sessionId, setSessionId] = useState('');
  const [message, setMessage] = useState('Hello, can you help me with my order?');
  const [results, setResults] = useState<any[]>([]);

  const { isHealthy, loading: healthLoading, refetch: checkHealth } = useHealthCheck();
  const { createSession, loading: createLoading } = useCreateSession();
  const { sendMessage, loading: sendLoading } = useSendChat();

  const addResult = (operation: string, result: any) => {
    setResults(prev => [...prev, {
      timestamp: new Date().toISOString(),
      operation,
      result: JSON.stringify(result, null, 2)
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
        // metadata: { source: 'test-component' }
      });

      addResult('Send Message', result);
    } catch (error) {
      addResult('Send Message', { error: error.message });
    }
  };

  const clearResults = () => {
    setResults([]);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
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
            <span className={`text-sm ${isHealthy ? 'text-green-600' : 'text-red-600'}`}>
              Status: {isHealthy ? 'Healthy' : 'Unhealthy'}
            </span>
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

          {/* Clear Results */}
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Test Results</h3>
            <Button onClick={clearResults} variant="outline" size="sm">
              Clear Results
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      <div className="space-y-4">
        {results.map((result, index) => (
          <Card key={index}>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm">{result.operation}</CardTitle>
                <span className="text-xs text-muted-foreground">
                  {new Date(result.timestamp).toLocaleTimeString()}
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-64">
                {result.result}
              </pre>
            </CardContent>
          </Card>
        ))}
      </div>

      {results.length === 0 && (
        <Card>
          <CardContent className="text-center py-8 text-muted-foreground">
            No test results yet. Try running some operations above.
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default TestGraphQL;
