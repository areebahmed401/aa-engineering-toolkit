import { HashRouter, Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { EngineProvider } from "./lib/engine";
import { PrefsProvider } from "./lib/prefs";
import { BatteryPage, BATTERY_TOOL } from "./pages/BatteryPage";
import { Home } from "./pages/Home";
import { StructuralPage } from "./pages/StructuralPage";
import { ToolPage } from "./pages/ToolPage";
import { VESSEL_TOOL_ID, VesselDesign } from "./pages/VesselDesign";

// Hash routing works on GitHub Pages without server-side rewrites.
export default function App() {
  return (
    <PrefsProvider>
      <EngineProvider>
        <HashRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Home />} />
              <Route path={`tool/${BATTERY_TOOL}`} element={<BatteryPage />} />
              <Route path={`tool/${VESSEL_TOOL_ID}`} element={<VesselDesign />} />
              <Route path="tool/:toolId" element={<ToolPage />} />
              <Route path="structural" element={<StructuralPage />} />
              <Route path="*" element={<div className="card p-6">Page not found. <Link className="text-primary underline" to="/">Home</Link></div>} />
            </Route>
          </Routes>
        </HashRouter>
      </EngineProvider>
    </PrefsProvider>
  );
}
