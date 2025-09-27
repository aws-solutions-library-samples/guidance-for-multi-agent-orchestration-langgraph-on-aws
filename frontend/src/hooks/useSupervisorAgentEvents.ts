import { useState, useEffect, useCallback, useRef } from 'react';
import { events, type EventsChannel } from "aws-amplify/api";
import type { AgentType } from '../types';

interface SupervisorMessage {
  type: string;
  data: any;
  agentType?: AgentType;
  timestamp?: string;
}

interface UseSupervisorAgentEventsReturn {
  messages: SupervisorMessage[];
  publishCustomerRequest: (message: string, sessionId: string, context?: any) => Promise<void>;
  isProcessing: boolean;
  streamingContent: string;
  streamingAgentType: AgentType | null;
  connectionStatus: 'connected' | 'connecting' | 'error' | 'disconnected';
  clearMessages: () => void;
}

export const useSupervisorAgentEvents = (
  sessionId: string | null
): UseSupervisorAgentEventsReturn => {
  const [messages, setMessages] = useState<SupervisorMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingAgentType, setStreamingAgentType] = useState<AgentType | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'error' | 'disconnected'>('disconnected');
  const channelRef = useRef<EventsChannel | null>(null);

  // Connect to response channel when session is available
  useEffect(() => {
    if (!sessionId) {
      setConnectionStatus('disconnected');
      return;
    }

    let channel: EventsChannel;
    
    const connectAndSubscribe = async () => {
      try {
        setConnectionStatus('connecting');
        
        // Connect to supervisor response channel
        const responseChannel = `/supervisor/${sessionId}/response`;
        channel = await events.connect(responseChannel);
        channelRef.current = channel;
        
        // Subscribe to messages
        channel.subscribe({
          next: (data: any) => {
            handleSupervisorMessage(data.event);
            setConnectionStatus('connected');
          },
          error: (err) => {
            console.error('Events subscription error:', err);
            setConnectionStatus('error');
          },
        });

        console.log(`Connected to channel: ${responseChannel}`);
      } catch (error) {
        console.error('Failed to connect to events channel:', error);
        setConnectionStatus('error');
      }
    };

    connectAndSubscribe();

    // Cleanup on unmount or session change
    return () => {
      if (channel) {
        channel.close();
        channelRef.current = null;
      }
    };
  }, [sessionId]);

  // Handle all supervisor agent message types from WEBSOCKET_INTEGRATION.md
  const handleSupervisorMessage = useCallback((messageData: any) => {
    const message: SupervisorMessage = {
      type: messageData.type,
      data: messageData.data,
      agentType: messageData.agentType as AgentType,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, message]);

    // Handle specific message types
    switch (messageData.type) {
      case 'processing_started':
      case 'request_processing_started':
        setIsProcessing(true);
        setStreamingContent('');
        setStreamingAgentType(null);
        break;

      case 'token_streaming_started':
        setStreamingContent('');
        setStreamingAgentType((messageData.agentType as AgentType) || null);
        break;

      case 'token':
        if (messageData.data?.content) {
          setStreamingContent(prev => prev + messageData.data.content);
        }
        break;

      case 'processing_complete':
      case 'request_processing_complete':
      case 'token_streaming_complete':
        setIsProcessing(false);
        // Keep streaming content for final display
        break;

      case 'error':
      case 'request_processing_error':
      case 'agent_error':
        setIsProcessing(false);
        setStreamingContent('');
        setStreamingAgentType(null);
        console.error('Supervisor agent error:', messageData.data);
        break;

      case 'progress':
      case 'state_update':
      case 'sub_agent_update':
      case 'agent_completed':
        // Handle progress updates
        break;

      default:
        console.log('Unhandled message type:', messageData.type);
    }
  }, []);

  // Publish customer request to supervisor agent
  const publishCustomerRequest = useCallback(async (
    message: string,
    sessionId: string,
    context: any = {}
  ): Promise<void> => {
    try {
      const incomingChannel = `/supervisor/incoming/${sessionId}`;
      const customerRequest = {
        type: "customer_request",
        data: {
          customer_message: message,
          session_id: sessionId,
          customer_id: "customer-123", // This should come from user context
          conversation_history: [],
          context: context
        }
      };

      await events.post(incomingChannel, customerRequest);
      console.log("Customer request published successfully");
    } catch (error) {
      console.error("Failed to publish customer request:", error);
      throw error;
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStreamingContent('');
    setStreamingAgentType(null);
    setIsProcessing(false);
  }, []);

  return {
    messages,
    publishCustomerRequest,
    isProcessing,
    streamingContent,
    streamingAgentType,
    connectionStatus,
    clearMessages
  };
};