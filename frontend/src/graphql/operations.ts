// GraphQL operations for AWS AppSync using Amplify
// These are string-based GraphQL operations for use with Amplify's generateClient()
// Updated to match the actual backend schema and resolver implementation

// Fragment definitions for reusable type structures
export const CHAT_MESSAGE_FRAGMENT = `
  fragment ChatMessageFragment on ChatMessage {
    id
    sessionId
    content
    sender
    timestamp
    agentResponse {
      agentType
      content
      confidence
      processingTime
      metadata
      timestamp
    }
    metadata
  }
`;

export const CHAT_SESSION_FRAGMENT = `
  fragment ChatSessionFragment on ChatSession {
    sessionId
    userId
    createdAt
    lastActivity
    status
    messageCount
    metadata
  }
`;

export const AGENT_STATUS_FRAGMENT = `
  fragment AgentStatusFragment on AgentStatus {
    agentId
    type
    status
    lastHeartbeat
    activeConnections
    averageResponseTime
    errorRate
    metadata
  }
`;

// Query operations
export const GET_SESSION = `
  ${CHAT_SESSION_FRAGMENT}
  ${CHAT_MESSAGE_FRAGMENT}
  query GetSession($sessionId: ID!) {
    getSession(sessionId: $sessionId) {
      ...ChatSessionFragment
      messages {
        ...ChatMessageFragment
      }
    }
  }
`;

export const GET_USER_SESSIONS = `
  ${CHAT_SESSION_FRAGMENT}
  query GetUserSessions($userId: ID!, $limit: Int, $nextToken: String) {
    getUserSessions(userId: $userId, limit: $limit, nextToken: $nextToken) {
      ...ChatSessionFragment
    }
  }
`;

export const GET_CHAT_HISTORY = `
  ${CHAT_MESSAGE_FRAGMENT}
  query GetChatHistory($sessionId: ID!, $limit: Int, $nextToken: String) {
    getChatHistory(sessionId: $sessionId, limit: $limit, nextToken: $nextToken) {
      ...ChatMessageFragment
    }
  }
`;

export const GET_ALL_AGENT_STATUSES = `
  ${AGENT_STATUS_FRAGMENT}
  query GetAllAgentStatuses {
    getAllAgentStatuses {
      ...AgentStatusFragment
    }
  }
`;

export const GET_AGENTS_BY_TYPE = `
  ${AGENT_STATUS_FRAGMENT}
  query GetAgentsByType($agentType: AgentType!) {
    getAgentsByType(agentType: $agentType) {
      ...AgentStatusFragment
    }
  }
`;

export const HEALTH_CHECK = `
  query HealthCheck {
    healthCheck
  }
`;

// Mutation operations - Updated to match backend implementation
export const SEND_CHAT = `
  mutation SendChat($input: SendChatInput!) {
    sendChat(input: $input) {
      success
      message {
        id
        sessionId
        content
        sender
        timestamp
        agentResponse {
          content
        }
        metadata
      }
      error
    }
  }
`;

export const CREATE_SESSION = `
  mutation CreateSession($input: CreateSessionInput!) {
    createSession(input: $input) {
      success
      session {
        sessionId
        userId
        createdAt
        lastActivity
        status
        messageCount
      }
      error
    }
  }
`;

export const CLOSE_SESSION = `
  mutation CloseSession($sessionId: ID!) {
    closeSession(sessionId: $sessionId) {
      success
      session {
        sessionId
        userId
        createdAt
        lastActivity
        status
        messageCount
        metadata
      }
      error
      timestamp
    }
  }
`;

export const EXECUTE_TASK_ON_AGENT = `
  mutation ExecuteTaskOnAgent($input: ExecuteTaskInput!) {
    executeTaskOnAgent(input: $input) {
      success
      taskResult {
        taskId
        agentType
        status
        result
        error
        startTime
        endTime
        processingTime
      }
      error
    }
  }
`;

// Subscription operations
export const ON_CHAT_MESSAGE = `
  subscription OnChatMessage($sessionId: ID!) {
    onChatMessage(sessionId: $sessionId) {
      success
      message {
        id
        sessionId
        content
        sender
        timestamp
        agentResponse {
          id
          content
          sender
          timestamp
          agentType
          metadata
        }
        metadata
      }
      error
      timestamp
    }
  }
`;

export const ON_AGENT_STATUS_CHANGE = `
  ${AGENT_STATUS_FRAGMENT}
  subscription OnAgentStatusChange {
    onAgentStatusChange {
      ...AgentStatusFragment
    }
  }
`;