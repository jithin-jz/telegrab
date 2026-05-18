import { Component, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-canvas flex h-screen w-screen items-center justify-center p-8">
          <div className="bg-surface border-hairline w-full max-w-md rounded-2xl border p-8 text-center shadow-2xl">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
              <AlertTriangle className="h-8 w-8 text-red-400" />
            </div>
            <h1 className="text-foreground mb-2 text-xl font-semibold">Something went wrong</h1>
            <p className="text-slate mb-6 text-sm">
              The application encountered an unexpected error. Please try reloading.
            </p>

            {this.state.error && (
              <details className="mb-6 text-left">
                <summary className="text-slate hover:text-foreground cursor-pointer text-xs transition-colors">
                  Technical Details
                </summary>
                <pre className="bg-canvas mt-2 max-h-32 overflow-auto rounded-lg p-3 text-xs text-red-400">
                  {this.state.error.message}
                </pre>
              </details>
            )}

            <button
              onClick={this.handleReload}
              className="bg-primary hover:bg-primary-pressed text-on-primary inline-flex items-center gap-2 rounded-lg px-6 py-3 font-medium transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
