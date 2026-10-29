import { useEffect } from "react";
import styles from "./App.module.css";
import { TopBar } from "./components/layout/TopBar";
import { KanbanBoard } from "./components/board/KanbanBoard";
import { LoginPage } from "./pages/LoginPage";
import { Spinner } from "./components/ui";
import { useSessionStore } from "./store/session";

export function App() {
  const { status, initSession } = useSessionStore();

  useEffect(() => {
    initSession();
  }, [initSession]);

  if (status === "loading" || status === "idle") {
    return (
      <div className={styles.loadingScreen}>
        <Spinner size="lg" />
        <span>Loading workspace…</span>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <LoginPage />;
  }

  return (
    <div className={styles.appRoot}>
      <TopBar />
      <KanbanBoard />
    </div>
  );
}
