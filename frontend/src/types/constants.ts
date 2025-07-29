// Application constants and utility types

import {
  AgentType,
  AgentHealthStatus,
  MessageSender,
  SessionStatus,
  TaskStatus
} from './enums';

// Agent Type Display Names
export const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  [AgentType.ORDER_MANAGEMENT]: 'Order Management',
  [AgentType.PRODUCT_RECOMMENDATION]: 'Product Recommendation',
  [AgentType.PERSONALIZATION]: 'Personalization',
  [AgentType.TROUBLESHOOTING]: 'Troubleshooting',
  [AgentType.SUPERVISOR]: 'Supervisor'
};

// Agent Type Descriptions
export const AGENT_TYPE_DESCRIPTIONS: Record<AgentType, string> = {
  [AgentType.ORDER_MANAGEMENT]: 'Handles order processing, tracking, and management',
  [AgentType.PRODUCT_RECOMMENDATION]: 'Provides personalized product recommendations',
  [AgentType.PERSONALIZATION]: 'Manages user preferences and personalization',
  [AgentType.TROUBLESHOOTING]: 'Assists with technical support and issue resolution',
  [AgentType.SUPERVISOR]: 'Coordinates and manages other agents'
};

// Status Display Names
export const AGENT_STATUS_LABELS: Record<AgentHealthStatus, string> = {
  [AgentHealthStatus.HEALTHY]: 'Healthy',
  [AgentHealthStatus.DEGRADED]: 'Degraded',
  [AgentHealthStatus.UNHEALTHY]: 'Unhealthy',
  [AgentHealthStatus.UNKNOWN]: 'Unknown'
};

export const SESSION_STATUS_LABELS: Record<SessionStatus, string> = {
  [SessionStatus.ACTIVE]: 'Active',
  [SessionStatus.CLOSED]: 'Closed',
  [SessionStatus.PAUSED]: 'Paused'
};

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: 'Pending',
  [TaskStatus.IN_PROGRESS]: 'In Progress',
  [TaskStatus.COMPLETED]: 'Completed',
  [TaskStatus.FAILED]: 'Failed'
};

export const MESSAGE_SENDER_LABELS: Record<MessageSender, string> = {
  [MessageSender.USER]: 'User',
  [MessageSender.AGENT]: 'Agent',
  [MessageSender.SYSTEM]: 'System'
};

// Status Colors for UI
export const AGENT_STATUS_COLORS: Record<AgentHealthStatus, string> = {
  [AgentHealthStatus.HEALTHY]: '#10B981', // green-500
  [AgentHealthStatus.DEGRADED]: '#F59E0B', // amber-500
  [AgentHealthStatus.UNHEALTHY]: '#EF4444', // red-500
  [AgentHealthStatus.UNKNOWN]: '#6B7280'   // gray-500
};

export const TASK_STATUS_COLORS: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: '#6B7280',    // gray-500
  [TaskStatus.IN_PROGRESS]: '#3B82F6', // blue-500
  [TaskStatus.COMPLETED]: '#10B981',   // green-500
  [TaskStatus.FAILED]: '#EF4444'      // red-500
};

// Default Values
export const DEFAULT_PAGINATION_LIMIT = 20;
export const DEFAULT_CHAT_HISTORY_LIMIT = 50;
export const DEFAULT_SESSION_TIMEOUT = 30 * 60 * 1000; // 30 minutes in milliseconds
export const DEFAULT_AGENT_REFRESH_INTERVAL = 5000; // 5 seconds
export const DEFAULT_MESSAGE_RETRY_ATTEMPTS = 3;
export const DEFAULT_CONNECTION_TIMEOUT = 10000; // 10 seconds

// WebSocket Event Types
export const WS_EVENT_TYPES = {
  CHAT_MESSAGE: 'chat_message',
  AGENT_STATUS_UPDATE: 'agent_status_update',
  SESSION_UPDATE: 'session_update',
  TASK_UPDATE: 'task_update',
  CONNECTION_STATUS: 'connection_status',
  ERROR: 'error'
} as const;

export type WSEventType = typeof WS_EVENT_TYPES[keyof typeof WS_EVENT_TYPES];

// Local Storage Keys
export const STORAGE_KEYS = {
  USER_ID: 'multi_agent_user_id',
  ACTIVE_SESSION: 'multi_agent_active_session',
  THEME_PREFERENCE: 'multi_agent_theme',
  CHAT_HISTORY: 'multi_agent_chat_history',
  USER_PREFERENCES: 'multi_agent_user_preferences'
} as const;

// API Endpoints (for REST fallback if needed)
export const API_ENDPOINTS = {
  HEALTH_CHECK: '/health',
  CHAT: '/chat',
  SESSIONS: '/sessions',
  AGENTS: '/agents',
  TASKS: '/tasks'
} as const;

// Error Codes
export const ERROR_CODES = {
  NETWORK_ERROR: 'NETWORK_ERROR',
  AUTHENTICATION_ERROR: 'AUTHENTICATION_ERROR',
  AUTHORIZATION_ERROR: 'AUTHORIZATION_ERROR',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  AGENT_UNAVAILABLE: 'AGENT_UNAVAILABLE',
  SESSION_EXPIRED: 'SESSION_EXPIRED',
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  INTERNAL_SERVER_ERROR: 'INTERNAL_SERVER_ERROR',
  GRAPHQL_ERROR: 'GRAPHQL_ERROR',
  WEBSOCKET_ERROR: 'WEBSOCKET_ERROR'
} as const;

export type ErrorCode = typeof ERROR_CODES[keyof typeof ERROR_CODES];

// Validation Rules
export const VALIDATION_RULES = {
  MESSAGE_MIN_LENGTH: 1,
  MESSAGE_MAX_LENGTH: 4000,
  SESSION_TITLE_MAX_LENGTH: 100,
  USER_ID_MIN_LENGTH: 1,
  USER_ID_MAX_LENGTH: 50,
  TASK_TIMEOUT_MIN: 1000,      // 1 second
  TASK_TIMEOUT_MAX: 300000,    // 5 minutes
  AGENT_ID_PATTERN: /^[a-zA-Z0-9_-]+$/
} as const;

// Feature Flags (for progressive rollout)
export const FEATURE_FLAGS = {
  ENABLE_VOICE_INPUT: false,
  ENABLE_FILE_UPLOAD: false,
  ENABLE_AGENT_SWITCHING: true,
  ENABLE_REAL_TIME_TYPING: true,
  ENABLE_MESSAGE_REACTIONS: false,
  ENABLE_DARK_MODE: true,
  ENABLE_ANALYTICS: true
} as const;

// Performance Thresholds
export const PERFORMANCE_THRESHOLDS = {
  SLOW_RESPONSE_TIME: 5000,     // 5 seconds
  VERY_SLOW_RESPONSE_TIME: 10000, // 10 seconds
  HIGH_ERROR_RATE: 0.1,         // 10%
  CRITICAL_ERROR_RATE: 0.25     // 25%
} as const;