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
      <div className="app-container">
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
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: '#f8fafc', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center' 
    }}>
      <div style={{ maxWidth: '28rem', width: '100%' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h1 style={{ 
            fontSize: '1.875rem', 
            fontWeight: '700', 
            color: '#1e293b', 
            marginBottom: '0.5rem' 
          }}>
            Welcome
          </h1>
          <p style={{ color: '#64748b' }}>
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
      <div style={{ 
        minHeight: '100vh', 
        backgroundColor: '#f8fafc', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center' 
      }}>
        <div style={{ textAlign: 'center' }}>
          <div className="animate-spin" style={{
            width: '2rem',
            height: '2rem',
            border: '2px solid #3b82f6',
            borderTopColor: 'transparent',
            borderRadius: '50%',
            margin: '0 auto 1rem'
          }}></div>
          <p style={{ color: '#64748b' }}>Loading...</p>
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
