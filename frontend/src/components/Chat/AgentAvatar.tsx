import React from 'react';
import { AgentType } from '../../types';
import { Avatar, AvatarFallback } from '../ui/avatar';
import { cn } from '../../lib/utils';

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
    className: 'agent-avatar-order',
    ariaLabel: 'Order Management Agent'
  },
  [AgentType.PRODUCT_RECOMMENDATION]: {
    name: 'Product Agent',
    icon: '🛍️',
    fallback: 'PR',
    className: 'agent-avatar-product',
    ariaLabel: 'Product Recommendation Agent'
  },
  [AgentType.PERSONALIZATION]: {
    name: 'Personal Agent',
    icon: '👤',
    fallback: 'PE',
    className: 'agent-avatar-personal',
    ariaLabel: 'Personalization Agent'
  },
  [AgentType.TROUBLESHOOTING]: {
    name: 'Support Agent',
    icon: '🔧',
    fallback: 'TS',
    className: 'agent-avatar-support',
    ariaLabel: 'Troubleshooting Support Agent'
  },
  [AgentType.SUPERVISOR]: {
    name: 'Supervisor',
    icon: '👨‍💼',
    fallback: 'SU',
    className: 'agent-avatar-supervisor',
    ariaLabel: 'Supervisor Agent'
  }
};

const sizeConfig = {
  sm: {
    avatar: 'h-6 w-6',
    text: 'text-xs',
    icon: 'text-xs'
  },
  md: {
    avatar: 'h-8 w-8',
    text: 'text-sm',
    icon: 'text-sm'
  },
  lg: {
    avatar: 'h-12 w-12',
    text: 'text-base',
    icon: 'text-lg'
  }
};

const AgentAvatar: React.FC<AgentAvatarProps> = ({ 
  agentType, 
  size = 'md', 
  showLabel = false,
  className = '' 
}) => {
  const config = agentConfig[agentType];
  const sizeStyles = sizeConfig[size];

  if (!config) {
    return null;
  }

  return (
    <div 
      className={cn("flex items-center gap-2", className)}
      role="img"
      aria-label={config.ariaLabel}
    >
      <Avatar 
        className={cn(
          sizeStyles.avatar,
          config.className,
          "transition-smooth hover:scale-105 focus-ring"
        )}
      >
        <AvatarFallback 
          className={cn(
            config.className,
            sizeStyles.icon,
            "font-medium select-none"
          )}
          title={config.name}
        >
          <span className="sr-only">{config.name}</span>
          <span aria-hidden="true">{config.icon}</span>
        </AvatarFallback>
      </Avatar>
      
      {showLabel && (
        <span 
          className={cn(
            sizeStyles.text, 
            "font-medium text-foreground",
            "hidden sm:inline-block" // Hide on mobile for space
          )}
          id={`agent-label-${agentType.toLowerCase()}`}
        >
          {config.name}
        </span>
      )}
    </div>
  );
};

export default AgentAvatar;
