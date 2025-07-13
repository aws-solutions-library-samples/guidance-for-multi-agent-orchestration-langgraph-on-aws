#!/usr/bin/env node

// Simple script to add test data to DynamoDB tables for GraphQL testing
// Run with: node add-test-data.js

const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');

// Initialize DynamoDB client
const client = new DynamoDBClient({ region: 'us-east-1' });
const docClient = DynamoDBDocumentClient.from(client);

// Table names (from CDK deployment)
const TABLES = {
  chatSessions: 'chat-sessions-dev',
  chatMessages: 'chat-messages-dev', 
  agentStatus: 'agent-status-dev'
};

// Test data
const testData = {
  chatSessions: [
    {
      sessionId: 'test-session-123',
      userId: 'test-user-123',
      createdAt: new Date().toISOString(),
      lastActivity: new Date().toISOString(),
      status: 'ACTIVE',
      messageCount: 2,
      metadata: { source: 'test', channel: 'web' }
    },
    {
      sessionId: 'test-session-456',
      userId: 'test-user-456',
      createdAt: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
      lastActivity: new Date(Date.now() - 1800000).toISOString(), // 30 min ago
      status: 'CLOSED',
      messageCount: 5,
      metadata: { source: 'test', channel: 'mobile' }
    }
  ],

  chatMessages: [
    {
      sessionId: 'test-session-123',
      messageId: 'msg-001',
      content: 'Hello, I need help with my order',
      sender: 'USER',
      timestamp: new Date(Date.now() - 300000).toISOString(), // 5 min ago
      userId: 'test-user-123',
      metadata: { channel: 'web' }
    },
    {
      sessionId: 'test-session-123',
      messageId: 'msg-002',
      content: 'I can help you with that. What is your order number?',
      sender: 'AGENT',
      timestamp: new Date(Date.now() - 240000).toISOString(), // 4 min ago
      userId: 'test-user-123',
      agentType: 'ORDER_MANAGEMENT',
      metadata: { agentId: 'order-agent-001', confidence: 0.95 }
    }
  ],

  agentStatus: [
    {
      agentId: 'order-agent-001',
      type: 'ORDER_MANAGEMENT',
      status: 'HEALTHY',
      lastHeartbeat: new Date().toISOString(),
      activeConnections: 3,
      averageResponseTime: 1.2,
      errorRate: 0.01,
      metadata: { version: '1.0.0', region: 'us-east-1' }
    },
    {
      agentId: 'product-agent-001',
      type: 'PRODUCT_RECOMMENDATION',
      status: 'HEALTHY',
      lastHeartbeat: new Date(Date.now() - 30000).toISOString(), // 30 sec ago
      activeConnections: 1,
      averageResponseTime: 0.8,
      errorRate: 0.005,
      metadata: { version: '1.0.0', region: 'us-east-1' }
    },
    {
      agentId: 'troubleshoot-agent-001',
      type: 'TROUBLESHOOTING',
      status: 'DEGRADED',
      lastHeartbeat: new Date(Date.now() - 120000).toISOString(), // 2 min ago
      activeConnections: 0,
      averageResponseTime: 3.5,
      errorRate: 0.15,
      metadata: { version: '1.0.0', region: 'us-east-1', issue: 'high_latency' }
    }
  ]
};

async function addTestData() {
  console.log('🚀 Adding test data to DynamoDB tables...\n');

  try {
    // Add chat sessions
    console.log('📝 Adding chat sessions...');
    for (const session of testData.chatSessions) {
      await docClient.send(new PutCommand({
        TableName: TABLES.chatSessions,
        Item: session
      }));
      console.log(`✅ Added session: ${session.sessionId}`);
    }

    // Add chat messages
    console.log('\n💬 Adding chat messages...');
    for (const message of testData.chatMessages) {
      await docClient.send(new PutCommand({
        TableName: TABLES.chatMessages,
        Item: message
      }));
      console.log(`✅ Added message: ${message.messageId}`);
    }

    // Add agent status
    console.log('\n🤖 Adding agent statuses...');
    for (const agent of testData.agentStatus) {
      await docClient.send(new PutCommand({
        TableName: TABLES.agentStatus,
        Item: agent
      }));
      console.log(`✅ Added agent: ${agent.agentId} (${agent.type})`);
    }

    console.log('\n🎉 Test data added successfully!');
    console.log('\n📋 You can now test these queries in AppSync Console:');
    console.log(`
1. Get existing session:
   query { getSession(sessionId: "test-session-123") { sessionId userId status messageCount } }

2. Get existing agent:
   query { getAgentStatus(agentId: "order-agent-001") { agentId type status activeConnections } }

3. Get degraded agent:
   query { getAgentStatus(agentId: "troubleshoot-agent-001") { agentId type status errorRate } }
    `);

  } catch (error) {
    console.error('❌ Error adding test data:', error);
    
    if (error.name === 'ResourceNotFoundException') {
      console.log('\n💡 Make sure the DynamoDB tables exist and the table names are correct.');
      console.log('Table names should be: chat-sessions-dev, chat-messages-dev, agent-status-dev');
    }
  }
}

// Run if called directly
if (require.main === module) {
  addTestData();
}

module.exports = { addTestData, testData };