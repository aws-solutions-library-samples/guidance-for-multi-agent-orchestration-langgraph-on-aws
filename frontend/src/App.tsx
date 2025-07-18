import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { useAuthenticator } from '@aws-amplify/ui-react';
import AuthenticatorWrapper from './components/auth/AuthenticatorWrapper';
import ChatInterface from './components/Chat/ChatInterface';
import TestGraphQL from './components/Chat/TestGraphQL';
import Header from './components/layout/Header';

// Authenticated App Component
function AuthenticatedApp() {
  return (
    <Router>
      <div className="app min-h-screen bg-background">
        <Header />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<ChatInterface />} />
            <Route path="/chat" element={<ChatInterface />} />
            <Route path="/test" element={<TestGraphQL />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

// Unauthenticated App Component
function UnauthenticatedApp() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Welcome
          </h1>
          <p className="text-gray-600">
            Please sign in to access your AI assistant
          </p>
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthenticatorWrapper>
      <AppContent />
    </AuthenticatorWrapper>
  );
}

// App Content that switches between authenticated and unauthenticated states
function AppContent() {
  const { authStatus } = useAuthenticator();

  // Show loading state while configuring
  if (authStatus === 'configuring') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Show authenticated app when user is signed in
  if (authStatus === 'authenticated') {
    return <AuthenticatedApp />;
  }

  // Show unauthenticated state (Authenticator will handle the UI)
  return <UnauthenticatedApp />;
}

export default App;
