import { Component, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { invoke } from '../lib/platform/core';

export type SectionName =
  | 'Sidebar'
  | 'FileExplorer'
  | 'PreviewModal'
  | 'MediaPlayer'
  | 'SettingsModal';

interface Props {
  section: SectionName;
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  retryKey: number;
}

/**
 * Independent error boundary for a specific UI section.
 * On crash: logs to the backend via cmd_log and shows a retry button that
 * re-mounts only the crashed section (by incrementing the key).
 */
export class SectionErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, retryKey: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const { section } = this.props;
    const stack = error.stack || '';
    const componentStack = errorInfo.componentStack || '';
    const logMessage = [
      `[ErrorBoundary] Section: ${section}`,
      `Message: ${error.message}`,
      `Stack: ${stack}`,
      `ComponentStack: ${componentStack}`,
    ].join('\n').slice(0, 2000);

    // Log to backend via cmd_log for diagnostics
    invoke('cmd_log', { message: logMessage }).catch(() => {
      // Swallow — if backend is also down we can't do anything
    });
  }

  handleRetry = () => {
    this.setState((prev) => ({
      hasError: false,
      error: null,
      retryKey: prev.retryKey + 1,
    }));
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full w-full items-center justify-center p-6">
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
              <AlertTriangle className="h-5 w-5 text-red-400" />
            </div>
            <p className="text-foreground text-sm font-medium">
              {this.props.section} crashed
            </p>
            {this.state.error && (
              <p className="text-muted-foreground max-w-xs text-xs">
                {this.state.error.message}
              </p>
            )}
            <button
              onClick={this.handleRetry}
              className="bg-primary hover:bg-primary-pressed text-on-primary mt-2 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </button>
          </div>
        </div>
      );
    }

    return <div key={this.state.retryKey} style={{ display: 'contents' }}>{this.props.children}</div>;
  }
}
