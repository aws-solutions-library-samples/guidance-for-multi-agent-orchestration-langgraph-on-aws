// UI-specific types for React components and state management

import type { AgentType, AgentHealthStatus, MessageSender, SessionStatus } from './enums';

// Forward declarations to avoid circular imports
interface ChatMessage {
  id: string;
  sessionId: string;
  content: string;
  sender: MessageSender;
  agentResponse?: any;
  metadata?: Record<string, any>;
}

interface ChatSession {
  sessionId: string;
  userId: string;
  createdAt: Date;
  lastActivity: Date;
  status: SessionStatus;
  messageCount: number;
  metadata?: Record<string, any>;
  messages?: ChatMessage[];
}

interface AgentStatus {
  agentId: string;
  type: AgentType;
  status: AgentHealthStatus;
  lastHeartbeat: Date;
  activeConnections: number;
  averageResponseTime?: number;
  errorRate?: number;
  metadata?: Record<string, any>;
}

// Component Props Types
export interface ChatInterfaceProps {
  sessionId?: string;
  onSessionChange?: (session: ChatSession) => void;
  onMessageSent?: (message: ChatMessage) => void;
}

export interface MessageListProps {
  messages: ChatMessage[];
  isLoading?: boolean;
  onRetry?: (messageId: string) => void;
}

export interface MessageInputProps {
  onSendMessage: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export interface AgentStatusIndicatorProps {
  agent: AgentStatus;
  showDetails?: boolean;
}

export interface SessionListProps {
  sessions: ChatSession[];
  activeSessionId?: string;
  onSessionSelect: (sessionId: string) => void;
  onSessionDelete?: (sessionId: string) => void;
}

// UI State Types
export interface ChatUIState {
  currentSession?: ChatSession;
  messages: ChatMessage[];
  isLoading: boolean;
  isConnected: boolean;
  error?: string;
  typingIndicator?: {
    agentType: AgentType;
    isTyping: boolean;
  };
}

export interface AgentDashboardState {
  agents: AgentStatus[];
  selectedAgent?: AgentStatus;
  refreshInterval: number;
  lastUpdated?: Date;
}

// Form Types
export interface MessageFormData {
  content: string;
  metadata?: Record<string, any>;
}

export interface SessionFormData {
  title?: string;
  metadata?: Record<string, any>;
}

// Theme and Styling Types
export interface ThemeConfig {
  primaryColor: string;
  secondaryColor: string;
  backgroundColor: string;
  textColor: string;
  borderColor: string;
  errorColor: string;
  successColor: string;
  warningColor: string;
}

export interface MessageTheme {
  userMessage: {
    backgroundColor: string;
    textColor: string;
    alignment: 'left' | 'right';
  };
  agentMessage: {
    backgroundColor: string;
    textColor: string;
    alignment: 'left' | 'right';
  };
  systemMessage: {
    backgroundColor: string;
    textColor: string;
    alignment: 'center';
  };
}

// Loading and Error States
export interface LoadingState {
  isLoading: boolean;
  loadingText?: string;
  progress?: number;
}

export interface ErrorState {
  hasError: boolean;
  error?: Error | string;
  errorCode?: string;
  canRetry: boolean;
}

// Notification Types
export interface NotificationConfig {
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  duration?: number;
  actions?: Array<{
    label: string;
    action: () => void;
  }>;
}

// Modal and Dialog Types
export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  size?: 'small' | 'medium' | 'large';
  closable?: boolean;
}

export interface ConfirmDialogProps extends ModalProps {
  message: string;
  onConfirm: () => void;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info';
}