// GraphQL-specific types and utilities

import type { AgentType, AgentHealthStatus, MessageSender, SessionStatus, TaskStatus } from './enums';

// Core GraphQL types
export interface ChatMessage {
  id: string;
  sessionId: string;
  content: string;
  sender: MessageSender;
  timestamp: string; // AWSDateTime as string
  agentResponse?: AgentResponse;
  metadata?: Record<string, any>;
}

export interface AgentResponse {
  agentType: AgentType;
  content: string;
  confidence?: number;
  processingTime?: number;
  metadata?: Record<string, any>;
  timestamp: string; // AWSDateTime as string
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

interface AgentStatus {
  agentId: string;
  type: AgentType;
  status: AgentHealthStatus;
  lastHeartbeat: Date;
  activeConnections: number;
  averageResponseTime?: number;
  errorRate?: number;
  metadata?: Record<string, any>;
}

interface TaskResult {
  taskId: string;
  agentType: AgentType;
  status: TaskStatus;
  result?: Record<string, any>;
  error?: string;
  startTime: Date;
  endTime?: Date;
  processingTime?: number;
}

interface AggregatedResponse {
  requestId: string;
  query: string;
  responses: any[];
  totalAgents: number;
  successfulResponses: number;
  failedResponses: number;
  averageResponseTime: number;
  timestamp: Date;
}

interface SendChatInput {
  sessionId: string;
  message: string;
  metadata?: Record<string, any>;
}

interface CreateSessionInput {
  userId: string;
  metadata?: Record<string, any>;
}

interface ExecuteTaskInput {
  agentType: AgentType;
  task: string;
  priority?: number;
  timeout?: number;
  metadata?: Record<string, any>;
}

interface AggregateDataInput {
  query: string;
  agentTypes?: AgentType[];
  timeout?: number;
  metadata?: Record<string, any>;
}

// GraphQL Query Result Types
export interface QueryResult<T> {
  data?: T;
  loading: boolean;
  error?: Error;
  refetch?: () => Promise<QueryResult<T>>;
}

export interface MutationResult<T> {
  data?: T;
  loading: boolean;
  error?: Error;
}

export interface SubscriptionResult<T> {
  data?: T;
  loading: boolean;
  error?: Error;
}

// Specific Query Types
export interface GetSessionQuery {
  getSession?: ChatSession;
}

export interface GetUserSessionsQuery {
  getUserSessions: ChatSession[];
}

export interface GetChatHistoryQuery {
  getChatHistory: ChatMessage[];
}

export interface GetAgentStatusQuery {
  getAgentStatus?: AgentStatus;
}

export interface GetAllAgentStatusesQuery {
  getAllAgentStatuses: AgentStatus[];
}

export interface GetAgentsByTypeQuery {
  getAgentsByType: AgentStatus[];
}

export interface GetTaskResultQuery {
  getTaskResult?: TaskResult;
}

export interface GetUserTasksQuery {
  getUserTasks: TaskResult[];
}

export interface HealthCheckQuery {
  healthCheck: string;
}

// Mutation Types
export interface SendChatMutation {
  sendChat: {
    success: boolean;
    message?: ChatMessage;
    error?: string;
  };
}

export interface CreateSessionMutation {
  createSession: {
    success: boolean;
    session?: ChatSession;
    error?: string;
  };
}

export interface CloseSessionMutation {
  closeSession: {
    success: boolean;
    session?: ChatSession;
    error?: string;
  };
}

export interface ExecuteTaskOnAgentMutation {
  executeTaskOnAgent: {
    success: boolean;
    taskResult?: TaskResult;
    error?: string;
  };
}

export interface AggregateDataFromAgentsMutation {
  aggregateDataFromAgents: AggregatedResponse;
}

export interface UpdateAgentStatusMutation {
  updateAgentStatus?: AgentStatus;
}

// Subscription Types
export interface OnChatMessageSubscription {
  onChatMessage: {
    success: boolean;
    message?: ChatMessage;
    error?: string;
  };
}

export interface OnSessionUpdateSubscription {
  onSessionUpdate: {
    success: boolean;
    session?: ChatSession;
    error?: string;
  };
}

export interface OnAgentStatusChangeSubscription {
  onAgentStatusChange: AgentStatus;
}

export interface OnAgentHealthChangeSubscription {
  onAgentHealthChange: AgentStatus;
}

export interface OnTaskCompleteSubscription {
  onTaskComplete: {
    success: boolean;
    taskResult?: TaskResult;
    error?: string;
  };
}

export interface OnAggregationCompleteSubscription {
  onAggregationComplete: AggregatedResponse;
}

// GraphQL Variables Types
export interface GetSessionVariables {
  sessionId: string;
}

export interface GetUserSessionsVariables {
  userId: string;
  limit?: number;
  nextToken?: string;
}

export interface GetChatHistoryVariables {
  sessionId: string;
  limit?: number;
  nextToken?: string;
}

export interface GetAgentStatusVariables {
  agentId?: string;
}

export interface GetAgentsByTypeVariables {
  agentType: AgentType;
}

export interface GetTaskResultVariables {
  taskId: string;
}

export interface GetUserTasksVariables {
  userId: string;
  limit?: number;
  nextToken?: string;
}

export interface SendChatVariables {
  input: SendChatInput;
}

export interface CreateSessionVariables {
  input: CreateSessionInput;
}

export interface CloseSessionVariables {
  sessionId: string;
}

export interface ExecuteTaskOnAgentVariables {
  input: ExecuteTaskInput;
}

export interface AggregateDataFromAgentsVariables {
  input: AggregateDataInput;
}

export interface UpdateAgentStatusVariables {
  agentId: string;
  status: string;
}

// Subscription Variables
export interface OnChatMessageVariables {
  sessionId: string;
}

export interface OnSessionUpdateVariables {
  userId: string;
}

export interface OnTaskCompleteVariables {
  userId: string;
}

export interface OnAggregationCompleteVariables {
  userId: string;
}

// GraphQL Error Types
export interface GraphQLFormattedError {
  message: string;
  locations?: Array<{
    line: number;
    column: number;
  }>;
  path?: Array<string | number>;
  extensions?: {
    code?: string;
    exception?: {
      stacktrace?: string[];
    };
  };
}

// Apollo Client specific types
export interface ApolloError {
  graphQLErrors: GraphQLFormattedError[];
  networkError?: Error;
  message: string;
}

// Cache Types
export interface CacheConfig {
  typePolicies?: Record<string, any>;
  possibleTypes?: Record<string, string[]>;
}

// Connection Types for Relay-style pagination
export interface Connection<T> {
  edges: Array<{
    node: T;
    cursor: string;
  }>;
  pageInfo: {
    hasNextPage: boolean;
    hasPreviousPage: boolean;
    startCursor?: string;
    endCursor?: string;
  };
}