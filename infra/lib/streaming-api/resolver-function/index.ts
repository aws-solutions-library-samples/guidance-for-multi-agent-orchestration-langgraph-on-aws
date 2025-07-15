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

// Metadata parsing utility
function parseMetadata(metadata: any): any {
  if (!metadata) {
    return {};
  }

  // If it's already an object, return it
  if (typeof metadata === 'object') {
    return metadata;
  }

  // If it's a string, try to parse it as JSON
  if (typeof metadata === 'string') {
    try {
      return JSON.parse(metadata);
    } catch (error) {
      console.log('Failed to parse metadata as JSON:', metadata);
      return { raw: metadata };
    }
  }

  // For any other type, wrap it in an object
  return { value: metadata };
}

// Main handler
export const handler: AppSyncResolverHandler<any, any> = async (
  event: AppSyncResolverEvent<any>,
  context: Context
) => {
  // Log the complete incoming event for debugging
  console.log('=== INCOMING GRAPHQL EVENT ===');
  console.log('Full Event:', JSON.stringify(event, null, 2));
  console.log('Context:', JSON.stringify({
    requestId: context.awsRequestId,
    functionName: context.functionName,
    functionVersion: context.functionVersion,
    remainingTimeInMillis: context.getRemainingTimeInMillis()
  }, null, 2));

  logger.info('GraphQL Resolver Event', {
    fieldName: event.info.fieldName,
    parentTypeName: event.info.parentTypeName,
    requestId: context.awsRequestId,
    arguments: event.arguments,
    identity: event.identity,
    source: event.source
  });

  try {
    // Validate configuration on cold start
    console.log('=== CONFIGURATION VALIDATION ===');
    console.log('Config:', JSON.stringify(config, null, 2));
    validateConfig();
    console.log('Configuration validation passed');

    const { fieldName, parentTypeName } = event.info;
    console.log(`Processing ${parentTypeName}.${fieldName}`);

    let result;
    switch (parentTypeName) {
      case 'Query':
        result = await handleQuery(event, context);
        break;
      case 'Mutation':
        result = await handleMutation(event, context);
        break;
      default:
        throw new Error(`Unknown GraphQL type: ${parentTypeName}`);
    }

    console.log('=== RESOLVER RESULT ===');
    console.log('Result:', JSON.stringify(result, null, 2));

    return result;
  } catch (error) {
    console.log('=== RESOLVER ERROR ===');
    console.log('Error:', error);
    console.log('Error Stack:', error instanceof Error ? error.stack : 'No stack trace');

    logger.error('Resolver error', error);
    const errorResponse = createErrorResponse(
      error instanceof Error ? error.message : 'Unknown error occurred',
      'RESOLVER_ERROR'
    );

    console.log('Error Response:', JSON.stringify(errorResponse, null, 2));
    return errorResponse;
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

    case 'sendChatStream':
      // Handle streaming chat - return async generator results
      const streamResults = [];
      for await (const chunk of handleSendChatStream(event.arguments)) {
        streamResults.push(chunk);
      }
      return streamResults;

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
import axios from 'axios';

// HTTP client for supervisor agent calls
const httpClient = axios.create({
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  },
  // No timeout - let agent take as much time as needed
  timeout: 0
});

// Circuit breaker for supervisor agent calls
class CircuitBreaker {
  private failures = 0;
  private isOpen = false;
  private lastFailureTime = 0;
  private readonly failureThreshold = 5;
  private readonly resetTimeout = 60000; // 1 minute

  private shouldAttemptReset(): boolean {
    return Date.now() - this.lastFailureTime > this.resetTimeout;
  }

  private onSuccess(): void {
    this.failures = 0;
    this.isOpen = false;
  }

  private onFailure(): void {
    this.failures++;
    this.lastFailureTime = Date.now();
    if (this.failures >= this.failureThreshold) {
      this.isOpen = true;
      console.log('Circuit breaker opened due to failures');
    }
  }

  async call<T>(fn: () => Promise<T>): Promise<T> {
    if (this.isOpen && this.shouldAttemptReset()) {
      console.log('Circuit breaker attempting reset');
      this.isOpen = false;
    }

    if (this.isOpen) {
      throw new Error('Supervisor agent is temporarily unavailable');
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
}

// Global circuit breaker instance
const supervisorCircuitBreaker = new CircuitBreaker();

// Supervisor agent client
async function callSupervisorAgent(sessionId: string, message: string, userId: string): Promise<any> {
  console.log('=== CALLING SUPERVISOR AGENT ===');
  console.log('Supervisor URL:', config.supervisorAgentUrl);

  const requestPayload = {
    customer_message: message,
    session_id: sessionId,
    customer_id: userId,
    conversation_history: [],
    context: {}
  };

  console.log('Request payload:', JSON.stringify(requestPayload, null, 2));

  try {
    const response = await supervisorCircuitBreaker.call(async () => {
      console.log('Making HTTP request to supervisor...');
      const result = await httpClient.post(`${config.supervisorAgentUrl}/process`, requestPayload);
      console.log('Supervisor response status:', result.status);
      console.log('Supervisor response data:', JSON.stringify(result.data, null, 2));
      return result.data;
    });

    return response;
  } catch (error) {
    console.log('=== SUPERVISOR AGENT ERROR ===');
    console.log('Error details:', error);

    if (axios.isAxiosError(error)) {
      console.log('Axios error response:', error.response?.data);
      console.log('Axios error status:', error.response?.status);
      console.log('Axios error message:', error.message);
    }

    // Return generic error message as requested
    throw new Error('Unable to process your request at the moment. Please try again later.');
  }
}

// Streaming supervisor agent client
async function* callSupervisorAgentStream(sessionId: string, message: string, userId: string): AsyncGenerator<any, void, unknown> {
  console.log('=== CALLING SUPERVISOR AGENT STREAM ===');
  console.log('Supervisor URL:', config.supervisorAgentUrl);

  const requestPayload = {
    customer_message: message,
    session_id: sessionId,
    customer_id: userId,
    conversation_history: [],
    context: {}
  };

  console.log('Request payload:', JSON.stringify(requestPayload, null, 2));

  try {
    // Create the streaming generator function
    const streamGenerator = async function* () {
      console.log('Making streaming HTTP request to supervisor...');

      // Use streaming endpoint if available, otherwise fall back to regular endpoint
      const streamEndpoint = `${config.supervisorAgentUrl}/process/stream`;

      try {
        const response = await httpClient.post(streamEndpoint, requestPayload, {
          responseType: 'stream'
        });

        console.log('Supervisor streaming response status:', response.status);

        // Parse streaming response
        let buffer = '';
        for await (const chunk of response.data) {
          buffer += chunk.toString();
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.trim()) {
              try {
                const data = JSON.parse(line);
                console.log('Streaming chunk:', data);
                yield data;
              } catch (parseError) {
                console.log('Failed to parse streaming chunk:', line);
              }
            }
          }
        }

        // Process any remaining buffer
        if (buffer.trim()) {
          try {
            const data = JSON.parse(buffer);
            console.log('Final streaming chunk:', data);
            yield data;
          } catch (parseError) {
            console.log('Failed to parse final chunk:', buffer);
          }
        }

      } catch (streamError) {
        console.log('Streaming endpoint not available, falling back to regular call');
        // Fall back to regular call
        const result = await httpClient.post(`${config.supervisorAgentUrl}/process`, requestPayload);
        console.log('Supervisor fallback response:', result.data);
        yield {
          type: 'final',
          data: result.data,
          session_id: sessionId,
          timestamp: Date.now()
        };
      }
    };

    // Use the circuit breaker with the streaming generator
    const generator = await supervisorCircuitBreaker.call(() => Promise.resolve(streamGenerator()));
    yield* generator;

  } catch (error) {
    console.log('=== SUPERVISOR AGENT STREAM ERROR ===');
    console.log('Error details:', error);

    if (axios.isAxiosError(error)) {
      console.log('Axios error response:', error.response?.data);
      console.log('Axios error status:', error.response?.status);
      console.log('Axios error message:', error.message);
    }

    // Yield error as stream
    yield {
      type: 'error',
      data: { error: 'Unable to process your request at the moment. Please try again later.' },
      session_id: sessionId,
      timestamp: Date.now()
    };
  }
}

// Save agent response to DynamoDB
async function saveAgentResponse(sessionId: string, userId: string, agentResponse: any): Promise<any> {
  console.log('=== SAVING AGENT RESPONSE ===');

  const messageId = uuidv4();
  const timestamp = new Date().toISOString();

  const agentMessage = {
    sessionId,
    messageId,
    content: agentResponse.response || agentResponse.message || 'Agent response received',
    sender: 'AGENT',
    timestamp,
    userId,
    agentType: agentResponse.agentType || 'SUPERVISOR',
    agentResponse: {
      agentType: agentResponse.agentType || 'SUPERVISOR',
      content: agentResponse.response || agentResponse.message || 'Agent response received',
      confidence: agentResponse.confidence || null,
      processingTime: agentResponse.processingTime || null,
      metadata: agentResponse.metadata || {},
      timestamp
    },
    metadata: {
      agentId: agentResponse.metadata?.agentId || 'supervisor-agent',
      confidence: agentResponse.confidence || null,
      processingTime: agentResponse.processingTime || null,
      ...agentResponse.metadata
    }
  };

  console.log('Agent message to save:', JSON.stringify(agentMessage, null, 2));

  // Save agent message to DynamoDB
  await docClient.send(new PutCommand({
    TableName: config.chatMessagesTable,
    Item: agentMessage
  }));

  // Update session message count
  await docClient.send(new UpdateCommand({
    TableName: config.chatSessionsTable,
    Key: { sessionId },
    UpdateExpression: 'SET lastActivity = :timestamp, messageCount = messageCount + :inc',
    ExpressionAttributeValues: {
      ':timestamp': timestamp,
      ':inc': 1
    }
  }));

  console.log('Agent response saved successfully');
  return agentMessage;
}

// Streaming chat resolver implementation
async function* handleSendChatStream(args: any): AsyncGenerator<any, void, unknown> {
  const { input } = args;
  const { sessionId, message, metadata } = input;

  console.log('=== SEND CHAT STREAM OPERATION ===');
  console.log('Input args:', JSON.stringify(args, null, 2));
  logger.info('SendChatStream called', { sessionId, messageLength: message?.length });

  try {
    // Validate input
    console.log('Validating input...');
    if (!sessionId || !message) {
      console.log('Validation failed: missing sessionId or message');
      yield createErrorResponse('SessionId and message are required', 'VALIDATION_ERROR');
      return;
    }
    console.log('Input validation passed');

    // Check if session exists
    console.log('Checking if session exists...');
    const sessionResult = await docClient.send(new GetCommand({
      TableName: config.chatSessionsTable,
      Key: { sessionId }
    }));

    if (!sessionResult.Item) {
      console.log('Session not found');
      yield createErrorResponse('Session not found', 'SESSION_NOT_FOUND');
      return;
    }
    console.log('Session found:', sessionResult.Item);

    // Create and save user message
    const messageId = uuidv4();
    const timestamp = new Date().toISOString();
    const chatMessage = {
      sessionId,
      messageId,
      content: message,
      sender: 'USER',
      timestamp,
      userId: sessionResult.Item.userId,
      metadata: parseMetadata(metadata)
    };

    // Save user message to DynamoDB
    await docClient.send(new PutCommand({
      TableName: config.chatMessagesTable,
      Item: chatMessage
    }));

    // Update session activity
    await docClient.send(new UpdateCommand({
      TableName: config.chatSessionsTable,
      Key: { sessionId },
      UpdateExpression: 'SET lastActivity = :timestamp, messageCount = messageCount + :inc',
      ExpressionAttributeValues: {
        ':timestamp': timestamp,
        ':inc': 1
      }
    }));

    // Yield initial user message confirmation
    yield createSuccessResponse({
      type: 'user_message_saved',
      message: {
        id: messageId,
        sessionId,
        content: message,
        sender: 'USER',
        timestamp,
        metadata: chatMessage.metadata
      }
    });

    // Stream from supervisor agent
    console.log('Starting supervisor agent stream...');
    let finalAgentResponse = null;

    try {
      for await (const streamUpdate of callSupervisorAgentStream(sessionId, message, sessionResult.Item.userId)) {
        // Forward streaming updates to client
        yield createSuccessResponse({
          type: 'agent_stream_update',
          data: streamUpdate,
          sessionId,
          timestamp: new Date().toISOString()
        });

        // Capture final response for saving
        if (streamUpdate.type === 'final' || streamUpdate.type === 'complete') {
          finalAgentResponse = streamUpdate.data;
        }
      }

      // Save final agent response to DynamoDB
      if (finalAgentResponse) {
        const agentMessage = await saveAgentResponse(sessionId, sessionResult.Item.userId, finalAgentResponse);

        // Yield final agent message
        yield createSuccessResponse({
          type: 'agent_message_saved',
          message: {
            id: agentMessage.messageId,
            content: agentMessage.content,
            sender: agentMessage.sender,
            timestamp: agentMessage.timestamp,
            agentType: agentMessage.agentType,
            metadata: agentMessage.metadata
          }
        });
      }

    } catch (supervisorError) {
      console.log('Supervisor agent streaming failed:', supervisorError);
      logger.error('Supervisor agent streaming error', supervisorError);

      // Save error message as agent response
      const errorMessage = supervisorError instanceof Error ? supervisorError.message : 'Unable to process your request at the moment. Please try again later.';

      const errorAgentMessage = await saveAgentResponse(sessionId, sessionResult.Item.userId, {
        response: errorMessage,
        agentType: 'SYSTEM',
        metadata: { error: true, originalError: supervisorError instanceof Error ? supervisorError.message : 'Unknown error' }
      });

      // Yield error response
      yield createSuccessResponse({
        type: 'agent_error',
        message: {
          id: errorAgentMessage.messageId,
          content: errorAgentMessage.content,
          sender: errorAgentMessage.sender,
          timestamp: errorAgentMessage.timestamp,
          agentType: errorAgentMessage.agentType,
          metadata: errorAgentMessage.metadata
        }
      });
    }

    // Yield completion marker
    yield createSuccessResponse({
      type: 'stream_complete',
      sessionId,
      timestamp: new Date().toISOString()
    });

    logger.info('Streaming message processing completed', { messageId, sessionId });

  } catch (error) {
    console.log('=== SEND CHAT STREAM ERROR ===');
    console.log('Error details:', error);
    logger.error('Error in sendChatStream', error);

    yield createErrorResponse('Failed to process streaming chat message', 'SEND_CHAT_STREAM_ERROR');
  }
}

// Chat resolver implementations
async function handleSendChat(args: any): Promise<any> {
  const { input } = args;
  const { sessionId, message, metadata } = input;

  console.log('=== SEND CHAT OPERATION ===');
  console.log('Input args:', JSON.stringify(args, null, 2));
  logger.info('SendChat called', { sessionId, messageLength: message?.length });

  try {
    // Validate input
    console.log('Validating input...');
    if (!sessionId || !message) {
      console.log('Validation failed: missing sessionId or message');
      return createErrorResponse('SessionId and message are required', 'VALIDATION_ERROR');
    }
    console.log('Input validation passed');

    // Check if session exists
    console.log('Checking if session exists...');
    console.log('Looking up session in table:', config.chatSessionsTable);
    const sessionResult = await docClient.send(new GetCommand({
      TableName: config.chatSessionsTable,
      Key: { sessionId }
    }));
    console.log('Session lookup result:', JSON.stringify(sessionResult, null, 2));

    if (!sessionResult.Item) {
      console.log('Session not found');
      return createErrorResponse('Session not found', 'SESSION_NOT_FOUND');
    }
    console.log('Session found:', sessionResult.Item);

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
      metadata: parseMetadata(metadata)
    };
    console.log('Created message record:', JSON.stringify(chatMessage, null, 2));

    // Save message to DynamoDB
    console.log('Saving message to table:', config.chatMessagesTable);
    await docClient.send(new PutCommand({
      TableName: config.chatMessagesTable,
      Item: chatMessage
    }));
    console.log('Message saved successfully');

    logger.info('Message saved successfully', { messageId, sessionId });

    // DEBUG: Check if execution continues
    console.log('DEBUG: About to update session activity...');

    // Update session last activity and message count
    console.log('Updating session activity...');
    await docClient.send(new UpdateCommand({
      TableName: config.chatSessionsTable,
      Key: { sessionId },
      UpdateExpression: 'SET lastActivity = :timestamp, messageCount = messageCount + :inc',
      ExpressionAttributeValues: {
        ':timestamp': timestamp,
        ':inc': 1
      }
    }));
    console.log('Session updated successfully');

    // Call supervisor agent for processing
    console.log('Calling supervisor agent...');
    let agentResponse = null;
    let agentMessage = null;

    try {
      agentResponse = await callSupervisorAgent(sessionId, message, sessionResult.Item.userId);
      console.log('Supervisor agent responded successfully');

      // Save agent response to DynamoDB
      agentMessage = await saveAgentResponse(sessionId, sessionResult.Item.userId, agentResponse);
      console.log('Agent response saved to DynamoDB');

    } catch (supervisorError) {
      console.log('Supervisor agent call failed:', supervisorError);
      logger.error('Supervisor agent error', supervisorError);

      // Save error message as agent response
      const errorMessage = supervisorError instanceof Error ? supervisorError.message : 'Unable to process your request at the moment. Please try again later.';

      agentMessage = await saveAgentResponse(sessionId, sessionResult.Item.userId, {
        response: errorMessage,
        agentType: 'SYSTEM',
        metadata: { error: true, originalError: supervisorError instanceof Error ? supervisorError.message : 'Unknown error' }
      });
      console.log('Error message saved as agent response');
    }

    logger.info('Message processing completed', { messageId, sessionId, hasAgentResponse: !!agentResponse });

    const response = createSuccessResponse({
      message: {
        id: messageId,
        sessionId,
        content: message,
        sender: 'USER',
        timestamp,
        metadata: chatMessage.metadata,
        agentResponse: agentMessage ? {
          id: agentMessage.messageId,
          content: agentMessage.content,
          sender: agentMessage.sender,
          timestamp: agentMessage.timestamp,
          agentType: agentMessage.agentType,
          metadata: agentMessage.metadata
        } : null
      }
    });
    console.log('SendChat response:', JSON.stringify(response, null, 2));
    return response;

  } catch (error) {
    console.log('=== SEND CHAT ERROR ===');
    console.log('Error details:', error);
    console.log('Error stack:', error instanceof Error ? error.stack : 'No stack');
    logger.error('Error in sendChat', error);
    return createErrorResponse('Failed to send chat message', 'SEND_CHAT_ERROR');
  }
}



async function handleCreateSession(args: any): Promise<any> {
  const { input } = args;
  const { userId, metadata } = input;

  console.log('=== CREATE SESSION OPERATION ===');
  console.log('Input args:', JSON.stringify(args, null, 2));
  console.log('Extracted userId:', userId, 'Type:', typeof userId);
  console.log('Extracted metadata:', metadata, 'Type:', typeof metadata);

  logger.info('CreateSession called', { userId });

  try {
    // Validate input
    console.log('Validating input...');
    if (!userId) {
      console.log('Validation failed: missing userId');
      return createErrorResponse('UserId is required', 'VALIDATION_ERROR');
    }
    console.log('Input validation passed');

    // Create new session
    console.log('Creating new session...');
    const sessionId = uuidv4();
    const timestamp = new Date().toISOString();
    console.log('Generated sessionId:', sessionId);
    console.log('Generated timestamp:', timestamp);

    // Parse metadata safely
    console.log('Parsing metadata...');
    const parsedMetadata = parseMetadata(metadata);
    console.log('Parsed metadata:', JSON.stringify(parsedMetadata, null, 2));

    const session = {
      sessionId,
      userId,
      createdAt: timestamp,
      lastActivity: timestamp,
      status: 'ACTIVE',
      messageCount: 0,
      metadata: parsedMetadata
    };

    console.log('Created session object:', JSON.stringify(session, null, 2));

    // Save session to DynamoDB
    console.log('Saving session to table:', config.chatSessionsTable);
    await docClient.send(new PutCommand({
      TableName: config.chatSessionsTable,
      Item: session
    }));
    console.log('Session saved successfully to DynamoDB');

    logger.info('Session created successfully', { sessionId, userId });

    const response = createSuccessResponse({
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

    console.log('CreateSession response:', JSON.stringify(response, null, 2));
    return response;

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