# Design Document

## Overview

The AppSync GraphQL Integration provides a modern, scalable API layer that connects frontend applications to the existing ECS-based multi-agent system. The architecture follows a serverless approach using AWS AppSync for GraphQL operations, Lambda for business logic, and maintains connectivity to the existing ECS infrastructure.

## Architecture

### High-Level Architecture

```
Frontend Applications
        ↓
    AWS AppSync (GraphQL API)
        ↓
    Lambda Resolvers
        ↓
    Existing ECS Supervisor Agent
        ↓
    Existing ECS Sub-Agents
```

### Network Architecture

- **VPC Integration**: Lambda functions deployed in the same VPC as ECS services
- **Private Subnets**: Lambda functions in private subnets with NAT gateway for external access
- **Security Groups**: Dedicated security groups for Lambda-to-ECS communication
- **Service Discovery**: Integration with AWS Cloud Map for dynamic service resolution

### Data Flow

1. **Request Flow**: Frontend → AppSync → Lambda → ECS Supervisor → ECS Sub-Agents
2. **Response Flow**: ECS Sub-Agents → ECS Supervisor → Lambda → AppSync → Frontend
3. **Real-time Updates**: AppSync Subscriptions for live chat and status updates
4. **Data Persistence**: DynamoDB for chat sessions and conversation history

## Components and Interfaces

### 1. AppSync GraphQL API

**Purpose**: Central GraphQL endpoint for all client interactions

**Key Features**:
- Cognito User Pool authentication
- Real-time subscriptions via WebSocket
- Schema-first API design
- Built-in caching and performance optimization

**Schema Operations**:
- `sendChat(sessionId: ID!, message: String!): ChatResponse`
- `executeTaskOnAgent(agentType: AgentType!, task: String!): TaskResponse`
- `aggregateDataFromAgents(query: String!): AggregatedResponse`
- `getAgentStatus(agentId: ID): AgentStatus`

### 2. Lambda Resolver Functions

**Purpose**: Business logic layer that bridges GraphQL operations to ECS services

**Core Functions**:
- **Chat Resolver**: Handles chat operations and DynamoDB persistence
- **Agent Task Resolver**: Routes tasks to specific agents via supervisor
- **Status Resolver**: Monitors agent health and availability
- **Aggregation Resolver**: Collects data from multiple agents

**Key Interfaces**:
```typescript
interface AgentClient {
  sendToSupervisor(request: AgentRequest): Promise<AgentResponse>
  getAgentStatus(agentId: string): Promise<AgentStatus>
  executeTask(agentType: string, task: string): Promise<TaskResult>
}

interface ChatManager {
  saveMessage(sessionId: string, message: ChatMessage): Promise<void>
  getSessionHistory(sessionId: string): Promise<ChatMessage[]>
  publishUpdate(sessionId: string, update: ChatUpdate): Promise<void>
}
```

### 3. Agent Communication Layer

**Purpose**: HTTP client for communicating with existing ECS services

**Features**:
- Circuit breaker pattern for fault tolerance
- Connection pooling for performance
- Retry logic with exponential backoff
- Health check integration

**Configuration**:
- Environment-based endpoint configuration
- Service discovery integration
- Load balancer awareness

### 4. DynamoDB Data Layer

**Purpose**: Persistent storage for chat sessions and conversation history

**Tables**:
- **ChatSessions**: Session metadata and user associations
- **ChatMessages**: Individual messages with timestamps and agent responses
- **AgentStatus**: Current status and health metrics for agents

**Access Patterns**:
- Query by session ID for conversation history
- Query by user ID for user's active sessions
- Query by timestamp for recent activity

## Data Models

### GraphQL Schema Types

```graphql
type ChatMessage {
  id: ID!
  sessionId: ID!
  content: String!
  sender: MessageSender!
  timestamp: AWSDateTime!
  agentResponse: AgentResponse
}

type AgentResponse {
  agentType: AgentType!
  content: String!
  confidence: Float
  metadata: AWSJSON
}

type AgentStatus {
  agentId: ID!
  type: AgentType!
  status: AgentHealthStatus!
  lastHeartbeat: AWSDateTime!
  activeConnections: Int!
}

enum AgentType {
  ORDER_MANAGEMENT
  PRODUCT_RECOMMENDATION
  PERSONALIZATION
  TROUBLESHOOTING
}

enum AgentHealthStatus {
  HEALTHY
  DEGRADED
  UNHEALTHY
  UNKNOWN
}
```

### DynamoDB Schema

```typescript
interface ChatSession {
  sessionId: string;        // Partition Key
  userId: string;
  createdAt: string;
  lastActivity: string;
  status: 'active' | 'closed';
  metadata: Record<string, any>;
}

interface ChatMessage {
  sessionId: string;        // Partition Key
  messageId: string;        // Sort Key
  content: string;
  sender: 'user' | 'agent';
  agentType?: string;
  timestamp: string;
  metadata: Record<string, any>;
}
```

## Error Handling

### Circuit Breaker Implementation

- **Failure Threshold**: 5 consecutive failures trigger circuit open
- **Timeout**: 30-second timeout for ECS service calls
- **Recovery**: Gradual recovery with half-open state testing

### Error Response Strategy

- **Service Unavailable**: Graceful degradation with cached responses
- **Partial Failures**: Return partial results with error indicators
- **Authentication Errors**: Clear error messages with retry guidance
- **Rate Limiting**: Exponential backoff with jitter

### Monitoring Integration

- **CloudWatch Metrics**: Custom metrics for circuit breaker state
- **X-Ray Tracing**: End-to-end request tracing
- **Structured Logging**: JSON-formatted logs for analysis

## Testing Strategy

### Unit Testing

- **Lambda Function Testing**: Mock ECS service responses
- **Agent Client Testing**: HTTP client behavior validation
- **GraphQL Resolver Testing**: Schema validation and response formatting
- **Circuit Breaker Testing**: Failure scenario simulation

### Integration Testing

- **End-to-End Flow Testing**: Complete request/response cycles
- **Real-time Subscription Testing**: WebSocket connection validation
- **Authentication Flow Testing**: Cognito integration verification
- **Database Operation Testing**: DynamoDB read/write operations

### Performance Testing

- **Load Testing**: Concurrent user simulation
- **Latency Testing**: Response time measurement
- **Throughput Testing**: Maximum requests per second
- **Stress Testing**: System behavior under extreme load

### Security Testing

- **Authentication Testing**: JWT token validation
- **Authorization Testing**: User permission enforcement
- **Input Validation Testing**: GraphQL query sanitization
- **WAF Testing**: Attack pattern detection

## Deployment Strategy

### Infrastructure as Code

- **AWS CDK**: TypeScript-based infrastructure definitions
- **Environment Configuration**: Separate stacks for dev/staging/prod
- **Resource Tagging**: Consistent tagging strategy for cost allocation
- **Security Policies**: Least privilege IAM roles and policies

### Monitoring and Observability

- **CloudWatch Dashboards**: Real-time system health visualization
- **Alarms**: Proactive alerting for system issues
- **Log Aggregation**: Centralized logging with search capabilities
- **Performance Metrics**: SLA monitoring and reporting

### Security Configuration

- **WAF Rules**: Protection against common web attacks
- **VPC Security**: Network isolation and access controls
- **Encryption**: Data encryption in transit and at rest
- **Compliance**: SOC 2 and other regulatory requirements