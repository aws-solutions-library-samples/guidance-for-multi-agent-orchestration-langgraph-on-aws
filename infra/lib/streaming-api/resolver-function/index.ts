import { AppSyncResolverEvent, AppSyncResolverHandler, Context } from 'aws-lambda';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';

// Environment configuration
interface Config {
  chatSessionsTable: string;
  chatMessagesTable: string;
  agentStatusTable: string;
  supervisorAgentUrl: string;
  environment: string;
  logLevel: string;
}

// Initialize configuration from environment variables (set by CDK)
const config: Config = {
  chatSessionsTable: process.env.CHAT_SESSIONS_TABLE || '',
  chatMessagesTable: process.env.CHAT_MESSAGES_TABLE || '',
  agentStatusTable: process.env.AGENT_STATUS_TABLE || '',
  supervisorAgentUrl: process.env.SUPERVISOR_AGENT_URL || 'http://supervisor-service:8000',
  environment: process.env.ENVIRONMENT || 'dev',
  logLevel: process.env.LOG_LEVEL || 'INFO'
};

// Initialize DynamoDB client
const dynamoClient = new DynamoDBClient({ region: process.env.AWS_REGION || 'us-east-1' });
const docClient = DynamoDBDocumentClient.from(dynamoClient);

// Logging utility
const logger = {
  info: (message: string, data?: any) => {
    if (config.logLevel === 'INFO' || config.logLevel === 'DEBUG') {
      console.log(JSON.stringify({ level: 'INFO', message, data, timestamp: new Date().toISOString() }));
    }
  },
  error: (message: string, error?: any) => {
    console.error(JSON.stringify({ level: 'ERROR', message, error: error?.message || error, timestamp: new Date().toISOString() }));
  },
  debug: (message: string, data?: any) => {
    if (config.logLevel === 'DEBUG') {
      console.log(JSON.stringify({ level: 'DEBUG', message, data, timestamp: new Date().toISOString() }));
    }
  }
};

// Validation utility
function validateConfig(): void {
  const requiredFields = ['chatSessionsTable', 'chatMessagesTable', 'agentStatusTable'];
  const missing = requiredFields.filter(field => !config[field as keyof Config]);
  
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }
}

// Error response utility
function createErrorResponse(message: string, code?: string): any {
  return {
    success: false,
    error: message,
    errorCode: code,
    timestamp: new Date().toISOString()
  };
}

// Success response utility
function createSuccessResponse(data: any): any {
  return {
    success: true,
    ...data,
    timestamp: new Date().toISOString()
  };
}

// Main handler
export const handler: AppSyncResolverHandler<any, any> = async (
  event: AppSyncResolverEvent<any>,
  context: Context
) => {
  logger.info('GraphQL Resolver Event', { 
    fieldName: event.info.fieldName, 
    parentTypeName: event.info.parentTypeName,
    requestId: context.awsRequestId 
  });
  
  try {
    // Validate configuration on cold start
    validateConfig();
    
    const { fieldName, parentTypeName } = event.info;
    
    switch (parentTypeName) {
      case 'Query':
        return await handleQuery(event, context);
      case 'Mutation':
        return await handleMutation(event, context);
      default:
        throw new Error(`Unknown GraphQL type: ${parentTypeName}`);
    }
  } catch (error) {
    logger.error('Resolver error', error);
    return createErrorResponse(
      error instanceof Error ? error.message : 'Unknown error occurred',
      'RESOLVER_ERROR'
    );
  }
};

// Query handler
async function handleQuery(event: AppSyncResolverEvent<any>, context: Context): Promise<any> {
  const { fieldName } = event.info;
  
  logger.debug('Handling query', { fieldName, arguments: event.arguments });
  
  switch (fieldName) {
    case 'healthCheck':
      return await handleHealthCheck();
    
    case 'getUserSessions':
      return await handleGetUserSessions(event.arguments);
    
    case 'getChatHistory':
      return await handleGetChatHistory(event.arguments);
    
    case 'getAllAgentStatuses':
      return await handleGetAllAgentStatuses();
    
    case 'getAgentsByType':
      return await handleGetAgentsByType(event.arguments);
    
    case 'getTaskResult':
      return await handleGetTaskResult(event.arguments);
    
    case 'getUserTasks':
      return await handleGetUserTasks(event.arguments);
    
    default:
      logger.error('Unknown query field', { fieldName });
      return createErrorResponse(`Query ${fieldName} not implemented`, 'NOT_IMPLEMENTED');
  }
}

// Mutation handler
async function handleMutation(event: AppSyncResolverEvent<any>, context: Context): Promise<any> {
  const { fieldName } = event.info;
  
  logger.debug('Handling mutation', { fieldName, arguments: event.arguments });
  
  switch (fieldName) {
    case 'sendChat':
      return await handleSendChat(event.arguments);
    
    case 'createSession':
      return await handleCreateSession(event.arguments);
    
    case 'closeSession':
      return await handleCloseSession(event.arguments);
    
    case 'executeTaskOnAgent':
      return await handleExecuteTaskOnAgent(event.arguments);
    
    case 'aggregateDataFromAgents':
      return await handleAggregateDataFromAgents(event.arguments);
    
    case 'updateAgentStatus':
      return await handleUpdateAgentStatus(event.arguments);
    
    default:
      logger.error('Unknown mutation field', { fieldName });
      return createErrorResponse(`Mutation ${fieldName} not implemented`, 'NOT_IMPLEMENTED');
  }
}

// Health check implementation
async function handleHealthCheck(): Promise<string> {
  logger.info('Health check requested');
  return 'Multi-Agent GraphQL API is healthy';
}

// Chat functionality implementations
import { PutCommand, GetCommand, QueryCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb';
import { v4 as uuidv4 } from 'uuid';

// Chat resolver implementations
async function handleSendChat(args: any): Promise<any> {
  const { input } = args;
  const { sessionId, message, metadata } = input;
  
  logger.info('SendChat called', { sessionId, messageLength: message?.length });
  
  try {
    // Validate input
    if (!sessionId || !message) {
      return createErrorResponse('SessionId and message are required', 'VALIDATION_ERROR');
    }

    // Check if session exists
    const sessionResult = await docClient.send(new GetCommand({
      TableName: config.chatSessionsTable,
      Key: { sessionId }
    }));

    if (!sessionResult.Item) {
      return createErrorResponse('Session not found', 'SESSION_NOT_FOUND');
    }

    // Create message record
    const messageId = uuidv4();
    const timestamp = new Date().toISOString();
    const chatMessage = {
      sessionId,
      messageId,
      content: message,
      sender: 'USER',
      timestamp,
      userId: sessionResult.Item.userId,
      metadata: metadata ? JSON.parse(metadata) : {}
    };

    // Save message to DynamoDB
    await docClient.send(new PutCommand({
      TableName: config.chatMessagesTable,
      Item: chatMessage
    }));

    // Update session last activity and message count
    await docClient.send(new UpdateCommand({
      TableName: config.chatSessionsTable,
      Key: { sessionId },
      UpdateExpression: 'SET lastActivity = :timestamp, messageCount = messageCount + :inc',
      ExpressionAttributeValues: {
        ':timestamp': timestamp,
        ':inc': 1
      }
    }));

    // TODO: Send to supervisor agent for processing (will be implemented in task 4.3)
    logger.info('Message saved successfully', { messageId, sessionId });

    return createSuccessResponse({
      message: {
        id: messageId,
        sessionId,
        content: message,
        sender: 'USER',
        timestamp,
        metadata: chatMessage.metadata
      }
    });

  } catch (error) {
    logger.error('Error in sendChat', error);
    return createErrorResponse('Failed to send chat message', 'SEND_CHAT_ERROR');
  }
}

async function handleCreateSession(args: any): Promise<any> {
  const { input } = args;
  const { userId, metadata } = input;
  
  logger.info('CreateSession called', { userId });
  
  try {
    // Validate input
    if (!userId) {
      return createErrorResponse('UserId is required', 'VALIDATION_ERROR');
    }

    // Create new session
    const sessionId = uuidv4();
    const timestamp = new Date().toISOString();
    const session = {
      sessionId,
      userId,
      createdAt: timestamp,
      lastActivity: timestamp,
      status: 'ACTIVE',
      messageCount: 0,
      metadata: metadata ? JSON.parse(metadata) : {}
    };

    // Save session to DynamoDB
    await docClient.send(new PutCommand({
      TableName: config.chatSessionsTable,
      Item: session
    }));

    logger.info('Session created successfully', { sessionId, userId });

    return createSuccessResponse({
      session: {
        sessionId,
        userId,
        createdAt: timestamp,
        lastActivity: timestamp,
        status: 'ACTIVE',
        messageCount: 0,
        metadata: session.metadata
      }
    });

  } catch (error) {
    logger.error('Error in createSession', error);
    return createErrorResponse('Failed to create session', 'CREATE_SESSION_ERROR');
  }
}

async function handleCloseSession(args: any): Promise<any> {
  const { sessionId } = args;
  
  logger.info('CloseSession called', { sessionId });
  
  try {
    // Validate input
    if (!sessionId) {
      return createErrorResponse('SessionId is required', 'VALIDATION_ERROR');
    }

    // Check if session exists
    const sessionResult = await docClient.send(new GetCommand({
      TableName: config.chatSessionsTable,
      Key: { sessionId }
    }));

    if (!sessionResult.Item) {
      return createErrorResponse('Session not found', 'SESSION_NOT_FOUND');
    }

    // Update session status
    const timestamp = new Date().toISOString();
    await docClient.send(new UpdateCommand({
      TableName: config.chatSessionsTable,
      Key: { sessionId },
      UpdateExpression: 'SET #status = :status, lastActivity = :timestamp',
      ExpressionAttributeNames: {
        '#status': 'status'
      },
      ExpressionAttributeValues: {
        ':status': 'CLOSED',
        ':timestamp': timestamp
      }
    }));

    logger.info('Session closed successfully', { sessionId });

    return createSuccessResponse({
      session: {
        ...sessionResult.Item,
        status: 'CLOSED',
        lastActivity: timestamp
      }
    });

  } catch (error) {
    logger.error('Error in closeSession', error);
    return createErrorResponse('Failed to close session', 'CLOSE_SESSION_ERROR');
  }
}

async function handleGetUserSessions(args: any): Promise<any> {
  const { userId, limit = 20, nextToken } = args;
  
  logger.info('GetUserSessions called', { userId, limit });
  
  try {
    // Validate input
    if (!userId) {
      return createErrorResponse('UserId is required', 'VALIDATION_ERROR');
    }

    // Query user sessions using GSI
    const queryParams: any = {
      TableName: config.chatSessionsTable,
      IndexName: 'UserIdIndex',
      KeyConditionExpression: 'userId = :userId',
      ExpressionAttributeValues: {
        ':userId': userId
      },
      ScanIndexForward: false, // Most recent first
      Limit: limit
    };

    if (nextToken) {
      queryParams.ExclusiveStartKey = JSON.parse(Buffer.from(nextToken, 'base64').toString());
    }

    const result = await docClient.send(new QueryCommand(queryParams));

    logger.info('User sessions retrieved', { userId, count: result.Items?.length || 0 });

    return result.Items || [];

  } catch (error) {
    logger.error('Error in getUserSessions', error);
    return createErrorResponse('Failed to get user sessions', 'GET_USER_SESSIONS_ERROR');
  }
}

async function handleGetChatHistory(args: any): Promise<any> {
  const { sessionId, limit = 50, nextToken } = args;
  
  logger.info('GetChatHistory called', { sessionId, limit });
  
  try {
    // Validate input
    if (!sessionId) {
      return createErrorResponse('SessionId is required', 'VALIDATION_ERROR');
    }

    // Query messages for session using timestamp index for chronological order
    const queryParams: any = {
      TableName: config.chatMessagesTable,
      IndexName: 'TimestampIndex',
      KeyConditionExpression: 'sessionId = :sessionId',
      ExpressionAttributeValues: {
        ':sessionId': sessionId
      },
      ScanIndexForward: true, // Chronological order
      Limit: limit
    };

    if (nextToken) {
      queryParams.ExclusiveStartKey = JSON.parse(Buffer.from(nextToken, 'base64').toString());
    }

    const result = await docClient.send(new QueryCommand(queryParams));

    logger.info('Chat history retrieved', { sessionId, count: result.Items?.length || 0 });

    return result.Items || [];

  } catch (error) {
    logger.error('Error in getChatHistory', error);
    return createErrorResponse('Failed to get chat history', 'GET_CHAT_HISTORY_ERROR');
  }
}

async function handleExecuteTaskOnAgent(args: any): Promise<any> {
  logger.info('ExecuteTaskOnAgent called', { agentType: args.input?.agentType });
  return createErrorResponse('ExecuteTaskOnAgent functionality will be implemented in task 4.4', 'NOT_IMPLEMENTED');
}

async function handleAggregateDataFromAgents(args: any): Promise<any> {
  logger.info('AggregateDataFromAgents called', { query: args.input?.query });
  return createErrorResponse('AggregateDataFromAgents functionality will be implemented in task 4.4', 'NOT_IMPLEMENTED');
}

async function handleUpdateAgentStatus(args: any): Promise<any> {
  logger.info('UpdateAgentStatus called', { agentId: args.agentId });
  return createErrorResponse('UpdateAgentStatus functionality will be implemented in task 4.4', 'NOT_IMPLEMENTED');
}

async function handleGetAllAgentStatuses(): Promise<any> {
  logger.info('GetAllAgentStatuses called');
  return createErrorResponse('GetAllAgentStatuses functionality will be implemented in task 4.4', 'NOT_IMPLEMENTED');
}

async function handleGetAgentsByType(args: any): Promise<any> {
  logger.info('GetAgentsByType called', { agentType: args.agentType });
  return createErrorResponse('GetAgentsByType functionality will be implemented in task 4.4', 'NOT_IMPLEMENTED');
}

async function handleGetTaskResult(args: any): Promise<any> {
  logger.info('GetTaskResult called', { taskId: args.taskId });
  return createErrorResponse('GetTaskResult functionality will be implemented in task 4.4', 'NOT_IMPLEMENTED');
}

async function handleGetUserTasks(args: any): Promise<any> {
  logger.info('GetUserTasks called', { userId: args.userId });
  return createErrorResponse('GetUserTasks functionality will be implemented in task 4.4', 'NOT_IMPLEMENTED');
}

// Export utilities for testing
export { config, logger, createErrorResponse, createSuccessResponse, docClient };