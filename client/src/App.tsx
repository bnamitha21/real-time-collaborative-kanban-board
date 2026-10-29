import { useEffect } from "react";
import styles from "./App.module.css";
import { TopBar } from "./components/layout/TopBar";
import { KanbanBoard } from "./components/board/KanbanBoard";
import { ActivityDrawer } from "./components/activity/ActivityDrawer";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LoginPage } from "./pages/LoginPage";
import { Spinner } from "./components/ui";
import { useSessionStore } from "./store/session";
import { connectSocket, disconnectSocket } from "./realtime/socket";

export function App() {
  const { status, initSession } = useSessionStore();

  useEffect(() => {
    initSession();
  }, [initSession]);

  useEffect(() => {
    if (status === "authenticated") {
      connectSocket();
    } else if (status === "unauthenticated") {
      disconnectSocket();
    }
    return () => {
      // Disconnect socket when App unmounts
      disconnectSocket();
    };
  }, [status]);

  if (status === "loading" || status === "idle") {
    return (
      <div className={styles.loadingScreen}>
        <Spinner size="lg" />
        <span>Loading workspace…</span>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return (
      <ErrorBoundary>
        <LoginPage />
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <div className={styles.appRoot}>
        <TopBar />
        <KanbanBoard />
        <ActivityDrawer />
      </div>
    </ErrorBoundary>
  );
}
