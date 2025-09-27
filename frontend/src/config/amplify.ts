import { Amplify } from 'aws-amplify';
import type { ResourcesConfig } from 'aws-amplify';

// Debug: Log environment variables to console for troubleshooting
console.log('Amplify Configuration Debug:');
console.log('VITE_USER_POOL_ID:', import.meta.env.VITE_USER_POOL_ID);
console.log('VITE_USER_POOL_CLIENT_ID:', import.meta.env.VITE_USER_POOL_CLIENT_ID);
console.log('VITE_GRAPHQL_API_URL:', import.meta.env.VITE_GRAPHQL_API_URL);
console.log('VITE_AWS_REGION:', import.meta.env.VITE_AWS_REGION);

// Validate required environment variables
const requiredEnvVars = {
    userPoolId: import.meta.env.VITE_USER_POOL_ID,
    userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID,
    graphqlApiUrl: import.meta.env.VITE_GRAPHQL_API_URL,
    awsRegion: import.meta.env.VITE_AWS_REGION
};

// Check for missing environment variables
const missingVars = Object.entries(requiredEnvVars)
    .filter(([key, value]) => !value)
    .map(([key]) => key);

if (missingVars.length > 0) {
    console.error('Missing required environment variables:', missingVars);
    console.error('Please ensure all VITE_* environment variables are set during build time');
}

const amplifyConfig: ResourcesConfig = {
    Auth: {
        Cognito: {
            userPoolId: requiredEnvVars.userPoolId || '',
            userPoolClientId: requiredEnvVars.userPoolClientId || '',
            loginWith: {
                email: true,
                username: false
            },
            signUpVerificationMethod: 'code',
            userAttributes: {
                email: {
                    required: true
                }
            },
            allowGuestAccess: false,
            passwordFormat: {
                minLength: 8,
                requireLowercase: true,
                requireUppercase: true,
                requireNumbers: true,
                requireSpecialCharacters: true
            }
        }
    },
    API: {
        GraphQL: {
            endpoint: requiredEnvVars.graphqlApiUrl || '',
            region: requiredEnvVars.awsRegion || 'us-east-1',
            defaultAuthMode: 'userPool'
        },
        Events: {
            // endpoint: import.meta.env.VITE_API_ENDPOINT || '',
            endpoint: "https://kz477vlbgjclxbxmc7vhwpf2iq.appsync-api.us-east-1.amazonaws.com/event",
            region: requiredEnvVars.awsRegion || 'us-east-1',
            defaultAuthMode: 'userPool'
        }
    }
};

// Validate configuration before initializing Amplify
if (!requiredEnvVars.userPoolId || !requiredEnvVars.userPoolClientId || !requiredEnvVars.graphqlApiUrl) {
    console.error('Amplify configuration is incomplete. Some features may not work correctly.');
    console.error('Current config:', {
        userPoolId: requiredEnvVars.userPoolId ? 'SET' : 'MISSING',
        userPoolClientId: requiredEnvVars.userPoolClientId ? 'SET' : 'MISSING',
        graphqlApiUrl: requiredEnvVars.graphqlApiUrl ? 'SET' : 'MISSING',
        awsRegion: requiredEnvVars.awsRegion || 'us-east-1 (default)'
    });
}

// Initialize Amplify with the configuration
Amplify.configure(amplifyConfig);

export default amplifyConfig;