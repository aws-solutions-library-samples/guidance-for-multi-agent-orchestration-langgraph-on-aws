#!/usr/bin/env node

/**
 * Configuration setup script for React Amplify Frontend
 * This script helps extract CDK stack outputs and configure environment variables
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Default configuration template
const defaultConfig = {
  VITE_AWS_REGION: 'us-east-1',
  VITE_USER_POOL_ID: '',
  VITE_USER_POOL_CLIENT_ID: '',
  VITE_IDENTITY_POOL_ID: '',
  VITE_GRAPHQL_API_URL: '',
  VITE_APP_TITLE: 'Multi-Agent Customer Support',
  VITE_APP_VERSION: '1.0.0'
};

/**
 * Extract configuration from CDK outputs
 * This function expects CDK outputs in the format:
 * {
 *   "StackName": {
 *     "UserPoolId": "us-east-1_XXXXXXXXX",
 *     "UserPoolClientId": "XXXXXXXXXXXXXXXXXXXXXXXXXX",
 *     "GraphQLApiUrl": "https://your-appsync-endpoint.appsync-api.region.amazonaws.com/graphql"
 *   }
 * }
 */
function extractFromCDKOutputs(cdkOutputsPath) {
  try {
    if (!fs.existsSync(cdkOutputsPath)) {
      console.warn(`CDK outputs file not found at ${cdkOutputsPath}`);
      return null;
    }

    const cdkOutputs = JSON.parse(fs.readFileSync(cdkOutputsPath, 'utf8'));
    
    // Find the streaming API stack (could be named differently based on environment)
    const stackKey = Object.keys(cdkOutputs).find(key => 
      key.includes('StreamingAPI') || key.includes('StreamingApi') || key.includes('streaming-api')
    );

    if (!stackKey) {
      console.warn('StreamingAPI stack not found in CDK outputs');
      console.log('Available stacks:', Object.keys(cdkOutputs));
      return null;
    }

    const stackOutputs = cdkOutputs[stackKey];
    
    return {
      VITE_USER_POOL_ID: stackOutputs.UserPoolId || stackOutputs.userPoolId || '',
      VITE_USER_POOL_CLIENT_ID: stackOutputs.UserPoolClientId || stackOutputs.userPoolClientId || '',
      VITE_IDENTITY_POOL_ID: stackOutputs.IdentityPoolId || stackOutputs.identityPoolId || '',
      VITE_GRAPHQL_API_URL: stackOutputs.GraphQLApiUrl || stackOutputs.graphQLApiUrl || ''
    };
  } catch (error) {
    console.error('Error reading CDK outputs:', error.message);
    return null;
  }
}

/**
 * Create .env file from configuration
 */
function createEnvFile(config, envPath) {
  const envContent = Object.entries(config)
    .map(([key, value]) => `${key}=${value}`)
    .join('\n');

  fs.writeFileSync(envPath, envContent);
  console.log(`Environment file created at ${envPath}`);
}

/**
 * Main setup function
 */
function setupConfig() {
  const args = process.argv.slice(2);
  const cdkOutputsPath = args[0] || '../infra/cdk.out/outputs.json';
  const envPath = path.join(__dirname, '../.env');

  console.log('Setting up Amplify configuration...');
  
  // Start with default configuration
  let config = { ...defaultConfig };

  // Try to extract from CDK outputs
  const cdkConfig = extractFromCDKOutputs(cdkOutputsPath);
  if (cdkConfig) {
    config = { ...config, ...cdkConfig };
    console.log('Configuration extracted from CDK outputs');
  } else {
    console.log('Using default configuration template');
    console.log('Please update the .env file with your actual CDK stack outputs');
  }

  // Create .env file
  createEnvFile(config, envPath);

  // Validate configuration
  const missingVars = Object.entries(config)
    .filter(([key, value]) => key.startsWith('VITE_') && key !== 'VITE_APP_TITLE' && key !== 'VITE_APP_VERSION' && !value)
    .map(([key]) => key);

  if (missingVars.length > 0) {
    console.warn('\nWarning: The following environment variables are empty:');
    missingVars.forEach(varName => console.warn(`  - ${varName}`));
    console.warn('\nPlease update these values in .env file with your CDK stack outputs');
  } else {
    console.log('\n✅ Configuration setup complete!');
  }

  console.log('\nNext steps:');
  console.log('1. Verify the .env file contains correct values');
  console.log('2. Run "npm run dev" to start the development server');
}

// Run setup if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  setupConfig();
}

export { setupConfig, extractFromCDKOutputs };