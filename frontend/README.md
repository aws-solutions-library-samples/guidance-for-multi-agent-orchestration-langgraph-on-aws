# React + Amplify Frontend

This is a React TypeScript application built with Vite and AWS Amplify for the Multi-Agent Customer Support system. It integrates with existing AWS infrastructure including Cognito for authentication and AppSync for GraphQL API.

## Features

- React 19 with TypeScript
- AWS Amplify integration with Cognito authentication
- AppSync GraphQL API integration
- React Router for navigation
- Responsive chat interface
- Environment-based configuration

## Setup

### Prerequisites

Ensure your AWS infrastructure is deployed using the CDK stack in the `infra/` directory.

### Installation

1. Install dependencies:
   ```bash
   npm install
   ```

2. Configure environment variables using one of these methods:

   **Option A: Automatic setup from CDK outputs (Recommended)**
   ```bash
   npm run setup-config:cdk
   ```

   **Option B: Manual setup**
   ```bash
   cp .env.example .env
   # Then edit .env with your CDK stack outputs
   ```

3. Verify your `.env` file contains the correct values from your CDK stack outputs:
   ```
   VITE_AWS_REGION=us-east-1
   VITE_USER_POOL_ID=us-east-1_XXXXXXXXX
   VITE_USER_POOL_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
   VITE_GRAPHQL_API_URL=https://your-appsync-endpoint.appsync-api.region.amazonaws.com/graphql
   ```

## Development

```bash
npm run dev
```

## Build

```bash
npm run build
```

## Configuration

### AWS Amplify Configuration

The application is configured to work with your existing AWS infrastructure:

- **Authentication**: Uses the existing Cognito User Pool created by the CDK stack
- **GraphQL API**: Connects to the existing AppSync GraphQL API
- **Authorization**: Uses Cognito User Pool authentication for GraphQL operations

### Environment Variables

The following environment variables must be set (populated from CDK stack outputs):

- `VITE_AWS_REGION`: AWS region where your resources are deployed
- `VITE_USER_POOL_ID`: Cognito User Pool ID from CDK stack output
- `VITE_USER_POOL_CLIENT_ID`: Cognito User Pool Client ID from CDK stack output
- `VITE_GRAPHQL_API_URL`: AppSync GraphQL API URL from CDK stack output
- `VITE_APP_TITLE`: Application title (optional)
- `VITE_APP_VERSION`: Application version (optional)

### Getting CDK Stack Outputs

To get the required values for your environment variables:

1. Navigate to the infrastructure directory:
   ```bash
   cd ../infra
   ```

2. Deploy the CDK stack (if not already deployed):
   ```bash
   npm run deploy
   ```

3. The outputs will be displayed after deployment, or you can find them in:
   - AWS CloudFormation console (Stack Outputs tab)
   - `infra/cdk.out/outputs.json` file (if it exists)

4. Use the setup script to automatically configure:
   ```bash
   cd ../frontend
   npm run setup-config:cdk
   ```

## Project Structure

```
src/
├── components/
│   └── Chat/
│       └── ChatInterface.tsx
├── config/
│   └── amplify.ts          # AWS Amplify configuration
├── types/
│   └── index.ts
├── App.tsx
└── main.tsx                # Amplify initialization
scripts/
└── setup-config.js         # Configuration setup script
```

## Authentication

The application uses AWS Cognito for authentication:

- Users must sign up/sign in to access the chat interface
- Authentication is handled by AWS Amplify UI components
- Sessions are managed automatically by Amplify
- GraphQL operations are authenticated using Cognito tokens

## Next Steps

1. ✅ Configure AWS Amplify with existing Cognito and AppSync resources
2. Implement authentication UI components
3. Build chat interface with GraphQL subscriptions
4. Add real-time message streaming
5. Implement error handling and loading states