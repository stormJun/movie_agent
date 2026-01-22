import { Navigate, Route, Routes } from "react-router-dom";
import { AdminLayout } from "./app/layout/AdminLayout";
import { ChatPage } from "./pages/ChatPage";
import { GraphExplorePage } from "./pages/GraphExplorePage";
import { GraphReasoningPage } from "./pages/GraphReasoningPage";
import { EntitiesPage } from "./pages/EntitiesPage";
import { RelationsPage } from "./pages/RelationsPage";
import { SourcesPage } from "./pages/SourcesPage";
import { SettingsPage } from "./pages/SettingsPage";

export function App() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/graph/explore" element={<GraphExplorePage />} />
        <Route path="/graph/reasoning" element={<GraphReasoningPage />} />
        <Route
          path="/graph/manage/entities"
          element={<EntitiesPage />}
        />
        <Route
          path="/graph/manage/relations"
          element={<RelationsPage />}
        />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
