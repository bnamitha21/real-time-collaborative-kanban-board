import { Component, type ReactNode, type ErrorInfo } from "react";
import styles from "./ErrorBoundary.module.css";
import { Button } from "./ui";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  private handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className={styles.container}>
          <h2 className={styles.title}>Something went wrong.</h2>
          <p className={styles.text}>Reload the page.</p>
          <Button variant="primary" size="md" onClick={this.handleReload}>
            Reload
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}

