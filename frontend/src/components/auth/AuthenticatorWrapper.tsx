import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import type { ReactNode } from 'react';

interface AuthenticatorWrapperProps {
  children: ReactNode;
}

export default function AuthenticatorWrapper({ children }: AuthenticatorWrapperProps) {
  return (
    <Authenticator>
      {children}
    </Authenticator>
  );
}