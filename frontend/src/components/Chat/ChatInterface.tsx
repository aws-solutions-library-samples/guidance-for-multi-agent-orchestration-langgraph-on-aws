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
      
      {/* Optional: Agent Activity Summary */}
      {Object.values(agentActivity).some(count => count > 0) && (
        <div className="flex-shrink-0 p-2 bg-gray-50 border-t text-xs text-gray-600">
          <div className="flex items-center gap-4">
            <span>Agent Activity:</span>
            {Object.entries(agentActivity).map(([type, count]) => 
              count > 0 && (
                <span key={type} className="flex items-center gap-1">
                  <span className="capitalize">{type.toLowerCase().replace('_', ' ')}</span>
                  <span className="bg-gray-200 px-1 rounded">{count}</span>
                </span>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;