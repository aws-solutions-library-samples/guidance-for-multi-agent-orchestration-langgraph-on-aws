import React from 'react';
import { AgentType } from '../../types';

interface AgentAvatarProps {
  agentType: AgentType;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

const agentConfig = {
  [AgentType.ORDER_MANAGEMENT]: {
    name: 'Order Agent',
    icon: '📦',
    fallback: 'OR',
    color: '#3b82f6',
    ariaLabel: 'Order Management Agent'
  },
  [AgentType.PRODUCT_RECOMMENDATION]: {
    name: 'Product Agent',
    icon: '🛍️',
    fallback: 'PR',
    color: '#10b981',
    ariaLabel: 'Product Recommendation Agent'
  },
  [AgentType.PERSONALIZATION]: {
    name: 'Personal Agent',
    icon: '👤',
    fallback: 'PE',
    color: '#8b5cf6',
    ariaLabel: 'Personalization Agent'
  },
  [AgentType.TROUBLESHOOTING]: {
    name: 'Support Agent',
    icon: '🔧',
    fallback: 'TS',
    color: '#ef4444',
    ariaLabel: 'Troubleshooting Support Agent'
  },
  [AgentType.SUPERVISOR]: {
    name: 'Supervisor',
    icon: '👨‍💼',
    fallback: 'SU',
    color: '#6b7280',
    ariaLabel: 'Supervisor Agent'
  }
};

const AgentAvatar: React.FC<AgentAvatarProps> = ({ 
  agentType, 
  size = 'md', 
  showLabel = false,
  className = '' 
}) => {
  const config = agentConfig[agentType];

  if (!config) {
    return null;
  }

  const avatarSize = size === 'sm' ? '1.5rem' : size === 'lg' ? '3rem' : '2rem';
  const fontSize = size === 'sm' ? '0.75rem' : size === 'lg' ? '1rem' : '0.875rem';
  const labelSize = size === 'sm' ? '0.75rem' : size === 'lg' ? '1rem' : '0.875rem';

  return (
    <div 
      className={`agent-avatar ${className}`}
      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
      role="img"
      aria-label={config.ariaLabel}
    >
      <div 
        className="agent-avatar"
        style={{
          width: avatarSize,
          height: avatarSize,
          backgroundColor: config.color,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: fontSize,
          fontWeight: '500',
          transition: 'all 0.2s',
          cursor: 'default'
        }}
        title={config.name}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'scale(1.05)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'scale(1)';
        }}
      >
        <span style={{ display: 'none' }}>{config.name}</span>
        <span aria-hidden="true">{config.icon}</span>
      </div>
      
      {showLabel && (
        <span 
          style={{
            fontSize: labelSize,
            fontWeight: '500',
            color: '#1e293b',
            display: window.innerWidth >= 640 ? 'inline-block' : 'none'
          }}
          id={`agent-label-${agentType.toLowerCase()}`}
        >
          {config.name}
        </span>
      )}
    </div>
  );
};

export default AgentAvatar;
