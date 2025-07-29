import { Amplify } from 'aws-amplify';
import type { ResourcesConfig } from 'aws-amplify';

const amplifyConfig: ResourcesConfig = {
    Auth: {
        Cognito: {
            userPoolId: import.meta.env.VITE_USER_POOL_ID || '',
            userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID || '',
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
            endpoint: import.meta.env.VITE_GRAPHQL_API_URL || '',
            region: import.meta.env.VITE_AWS_REGION || 'us-east-1',
            defaultAuthMode: 'userPool'
        }
    }
};

// Initialize Amplify with the configuration
// Amplify.configure(outputs);
Amplify.configure(amplifyConfig)
export default amplifyConfig;