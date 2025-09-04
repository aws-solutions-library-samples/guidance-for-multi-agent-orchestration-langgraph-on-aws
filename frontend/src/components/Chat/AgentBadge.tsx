import React from 'react';
import { AgentType } from '../../types';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';

interface AgentBadgeProps {
  agentType: AgentType;
  confidence?: number;
  processingTime?: number;
  size?: 'sm' | 'md';
  showMetrics?: boolean;
  className?: string;
}

const agentConfig = {
  [AgentType.ORDER_MANAGEMENT]: {
    name: 'Order',
    variant: 'info' as const,
    ariaLabel: 'Order Management Agent'
  },
  [AgentType.PRODUCT_RECOMMENDATION]: {
    name: 'Product',
    variant: 'success' as const,
    ariaLabel: 'Product Recommendation Agent'
  },
  [AgentType.PERSONALIZATION]: {
    name: 'Personal',
    variant: 'secondary' as const,
    ariaLabel: 'Personalization Agent'
  },
  [AgentType.TROUBLESHOOTING]: {
    name: 'Support',
    variant: 'destructive' as const,
    ariaLabel: 'Troubleshooting Support Agent'
  },
  [AgentType.SUPERVISOR]: {
    name: 'Supervisor',
    variant: 'outline' as const,
    ariaLabel: 'Supervisor Agent'
  }
};

const AgentBadge: React.FC<AgentBadgeProps> = ({ 
  agentType, 
  confidence,
  processingTime,
  size = 'sm',
  showMetrics = true,
  className = '' 
}) => {
  const config = agentConfig[agentType];
  
  if (!config) {
    return null;
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const formatProcessingTime = (time: number) => {
    return time < 1000 
      ? `${Math.round(time)}ms`
      : `${(time / 1000).toFixed(1)}s`;
  };

  return (
    <div 
      className={cn("flex items-center gap-2 flex-wrap", className)}
      role="group"
      aria-label={`${config.ariaLabel} information`}
    >
      <Badge 
        variant={config.variant}
        className={cn(
          "transition-smooth hover:scale-105 focus-ring",
          size === 'sm' ? 'text-2xs px-2 py-0.5' : 'text-xs px-3 py-1'
        )}
        aria-label={config.ariaLabel}
      >
        {config.name}
      </Badge>
      
      {showMetrics && (
        <div 
          className="flex items-center gap-2 text-xs text-muted-foreground"
          role="group"
          aria-label="Agent performance metrics"
        >
          {confidence !== undefined && (
            <div 
              className="flex items-center gap-1"
              role="group"
              aria-label={`Confidence score: ${Math.round(confidence * 100)} percent`}
            >
              <span className="text-muted-foreground/70 hidden sm:inline">
                Confidence:
              </span>
              <span 
                className={cn(
                  "font-medium transition-smooth",
                  getConfidenceColor(confidence)
                )}
                aria-live="polite"
              >
                {Math.round(confidence * 100)}%
              </span>
            </div>
          )}
          
          {processingTime !== undefined && (
            <div 
              className="flex items-center gap-1"
              role="group"
              aria-label={`Processing time: ${formatProcessingTime(processingTime)}`}
            >
              <span className="text-muted-foreground/70 hidden sm:inline">
                Time:
              </span>
              <span 
                className="font-medium text-muted-foreground"
                aria-live="polite"
              >
                {formatProcessingTime(processingTime)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AgentBadge;
