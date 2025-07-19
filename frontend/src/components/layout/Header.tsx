import { useAuth, useUserAttributes } from '../../hooks/useAuth';

export default function Header() {
  const { signOut, isLoading } = useAuth();
  const { email, username } = useUserAttributes();

  const handleSignOut = async () => {
    if (!isLoading) {
      await signOut();
    }
  };

  return (
    <header className="app-header">
      <div className="header-container">
        <div className="header-content">
          {/* Logo/Title */}
          <div>
            <h1 className="header-title">
              Multi-Agent Customer Support
            </h1>
          </div>

          {/* User Profile and Actions */}
          <div className="header-user-section">
            {/* User Info */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {/* User Avatar */}
                <div className="user-avatar">
                  <span>
                    {(username || email || 'U').charAt(0).toUpperCase()}
                  </span>
                </div>
                
                {/* User Details */}
                <div className="user-info">
                  <p className="user-name">
                    {username || 'User'}
                  </p>
                  {email && (
                    <p className="user-email">
                      {email}
                    </p>
                  )}
                </div>
              </div>

              {/* Logout Button */}
              <button
                onClick={handleSignOut}
                disabled={isLoading}
                className="logout-button"
                aria-label="Sign out"
              >
                {isLoading ? (
                  <div className="animate-spin" style={{
                    width: '1rem',
                    height: '1rem',
                    border: '2px solid #64748b',
                    borderTopColor: 'transparent',
                    borderRadius: '50%'
                  }}></div>
                ) : (
                  <>
                    <svg
                      style={{ width: '1rem', height: '1rem', marginRight: '0.25rem' }}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                      />
                    </svg>
                    <span className="user-info" style={{ display: 'inline' }}>Sign Out</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}