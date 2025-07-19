import React, { useState } from 'react';
import MultiAgentChatInterface from './MultiAgentChatInterface';
import { AgentType } from '../../types';

interface ChatInterfaceProps {
  className?: string;
  initialSessionId?: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ 
  className = '',
  initialSessionId 
}) => {
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(initialSessionId);
  const [agentActivity, setAgentActivity] = useState<Record<AgentType, number>>({
    [AgentType.ORDER_MANAGEMENT]: 0,
    [AgentType.PRODUCT_RECOMMENDATION]: 0,
    [AgentType.PERSONALIZATION]: 0,
    [AgentType.TROUBLESHOOTING]: 0,
    [AgentType.SUPERVISOR]: 0
  });

  const handleSessionCreate = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    console.log('New session created:', sessionId);
  };

  const handleAgentResponse = (agentType: AgentType, message: any) => {
    setAgentActivity(prev => ({
      ...prev,
      [agentType]: prev[agentType] + 1
    }));
    
    console.log(`Agent ${agentType} responded:`, message);
  };

  return (
    <div className={`h-full flex flex-col ${className}`}>
      <MultiAgentChatInterface
        sessionId={currentSessionId}
        onSessionCreate={handleSessionCreate}
        onAgentResponse={handleAgentResponse}
        className="flex-1"
      />
    </div>
  );
};

export default ChatInterface;