import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { load } from "@tauri-apps/plugin-store";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthWizard } from "./components/AuthWizard";
import { Dashboard } from "./components/Dashboard";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { UpdateBanner } from "./components/UpdateBanner";
import { TitleBar } from "./components/TitleBar";
import { useUpdateCheck } from "./hooks/useUpdateCheck";
import "./styles/globals.css";

import { Toaster } from "sonner";
import { ConfirmProvider } from "./contexts/ConfirmContext";
import { SettingsProvider } from "./contexts/SettingsContext";
import { DropZoneProvider } from "./contexts/DropZoneContext";

const queryClient = new QueryClient();

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

function AppContent() {
  const [authStatus, setAuthStatus] = useState<AuthStatus>("loading");
  const { available, version, downloading, progress, downloadAndInstall, dismissUpdate } = useUpdateCheck();

  // On mount: check for a saved session and auto-restore it.
  // This is the SINGLE source of truth for the initial connection.
  // useTelegramConnection (inside Dashboard) no longer calls cmd_connect on mount.
  useEffect(() => {
    const checkSession = async () => {
      try {
        const store = await load("config.json");
        const savedId = await store.get<string>("api_id");

        if (!savedId) {
          setAuthStatus("unauthenticated");
          return;
        }

        const apiId = parseInt(savedId, 10);
        if (isNaN(apiId)) {
          setAuthStatus("unauthenticated");
          return;
        }

        // Initialize the client with the saved API ID
        await invoke("cmd_connect", { apiId });

        // Verify the session is still valid with Telegram servers
        const ok = await invoke<boolean>("cmd_check_connection");
        if (ok) {
          setAuthStatus("authenticated");
        } else {
          setAuthStatus("unauthenticated");
        }
      } catch (err) {
        console.warn("Session restore failed, showing login:", err);
        // Session file is corrupt or revoked — clean up and show login
        try {
          const store = await load("config.json");
          await store.delete("api_id");
          await store.save();
        } catch {
          // best-effort cleanup
        }
        setAuthStatus("unauthenticated");
      }
    };

    checkSession();
  }, []);

  // Styled splash screen while verifying the session
  if (authStatus === "loading") {
    return (
      <main className="h-screen w-screen flex items-center justify-center bg-canvas">
        <div className="flex flex-col items-center gap-6">
          <div className="relative">
            <div className="w-16 h-16 rounded-2xl auth-glass border-hairline flex items-center justify-center shadow-2xl animate-pulse">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
                <path d="M12 2v8" />
                <path d="m16 6-4 4-4-4" />
                <rect width="20" height="8" x="2" y="14" rx="2" />
                <path d="M6 18h.01" />
                <path d="M10 18h.01" />
              </svg>
            </div>
            <div className="absolute -inset-4 bg-primary/10 blur-2xl rounded-full -z-10 animate-pulse" />
          </div>
          <div className="flex flex-col items-center gap-2">
            <h2 className="text-xl font-semibold tracking-tight text-foreground">Telegram Drive</h2>
            <p className="text-[13px] text-stone font-medium animate-pulse">Initializing secure connection...</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="h-screen w-screen text-foreground overflow-hidden selection:bg-primary/30 relative flex flex-col">
      <TitleBar />
      <UpdateBanner
        available={available}
        version={version}
        downloading={downloading}
        progress={progress}
        onUpdate={downloadAndInstall}
        onDismiss={dismissUpdate}
      />
      <Toaster theme="dark" position="bottom-center" toastOptions={{
        style: {
          background: 'var(--color-surface)',
          backdropFilter: 'blur(12px)',
          border: '1px solid var(--color-hairline)',
          color: 'var(--color-ink)'
        }
      }} />
      {authStatus === "authenticated" ? (
        <Dashboard onLogout={() => setAuthStatus("unauthenticated")} />
      ) : (
        <AuthWizard onLogin={() => setAuthStatus("authenticated")} />
      )}
    </main>
  );
}


function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ConfirmProvider>
          <SettingsProvider>
            <DropZoneProvider>
              <AppContent />
            </DropZoneProvider>
          </SettingsProvider>
        </ConfirmProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
