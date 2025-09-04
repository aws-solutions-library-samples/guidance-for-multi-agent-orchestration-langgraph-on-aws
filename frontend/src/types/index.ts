// Re-export enums from separate file to avoid circular imports
export * from './enums';
import type { MessageSender, AgentType, AgentHealthStatus, SessionStatus, TaskStatus } from './enums';

// Core Types
export interface ChatMessage {
  id: string;
  sessionId: string;
  content: string;
  sender: MessageSender;
  timestamp: string; // AWSDateTime as string from GraphQL
  agentResponse?: AgentResponse;
  metadata?: Record<string, any>;
}

export interface AgentResponse {
  agentType: AgentType;
  content: string;
  confidence?: number;
  processingTime?: number;
  metadata?: Record<string, any>;
  timestamp: string; // AWSDateTime as string from GraphQL
}

export interface ChatSession {
  sessionId: string;
  userId: string;
  createdAt: Date;
  lastActivity: Date;
  status: SessionStatus;
  messageCount: number;
  metadata?: Record<string, any>;
  messages?: ChatMessage[];
}

export interface AgentStatus {
  agentId: string;
  type: AgentType;
  status: AgentHealthStatus;
  lastHeartbeat: Date;
  activeConnections: number;
  averageResponseTime?: number;
  errorRate?: number;
  metadata?: Record<string, any>;
}

export interface TaskResult {
  taskId: string;
  agentType: AgentType;
  status: TaskStatus;
  result?: Record<string, any>;
  error?: string;
  startTime: Date;
  endTime?: Date;
  processingTime?: number;
}

export interface AggregatedResponse {
  requestId: string;
  query: string;
  responses: AgentResponse[];
  totalAgents: number;
  successfulResponses: number;
  failedResponses: number;
  averageResponseTime: number;
  timestamp: Date;
}

// Response Types
export interface ChatResponse {
  success: boolean;
  message?: ChatMessage;
  error?: string;
}

export interface TaskResponse {
  success: boolean;
  taskResult?: TaskResult;
  error?: string;
}

export interface SessionResponse {
  success: boolean;
  session?: ChatSession;
  error?: string;
}

// Input Types
export interface SendChatInput {
  sessionId: string;
  message: string;
  metadata?: Record<string, any>;
}

export interface CreateSessionInput {
  userId: string;
  metadata?: Record<string, any>;
}

export interface ExecuteTaskInput {
  agentType: AgentType;
  task: string;
  priority?: number;
  timeout?: number;
  metadata?: Record<string, any>;
}

export interface AggregateDataInput {
  query: string;
  agentTypes?: AgentType[];
  timeout?: number;
  metadata?: Record<string, any>;
}

// Streaming and Real-time Types
export interface StreamingResponse {
  content: string;
  agentType: AgentType;
  isComplete: boolean;
  timestamp?: Date;
}

export interface SubscriptionEvent<T> {
  data: T;
  timestamp: Date;
}

// Error Types
export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, any>;
}

export interface GraphQLError {
  message: string;
  locations?: Array<{
    line: number;
    column: number;
  }>;
  path?: Array<string | number>;
  extensions?: Record<string, any>;
}

// Pagination Types
export interface PaginationInput {
  limit?: number;
  nextToken?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  nextToken?: string;
  hasMore: boolean;
}