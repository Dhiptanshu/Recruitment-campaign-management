import { NavLink, Route, Routes } from "react-router-dom";
import { CandidatesPage } from "./pages/CandidatesPage";
import { CampaignsPage } from "./pages/CampaignsPage";
import { CampaignDetailPage } from "./pages/CampaignDetailPage";
import { ScreeningDetailPage } from "./pages/ScreeningDetailPage";

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-lg px-3 py-2 text-sm font-medium ${
          isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-sm font-bold text-white">GV</div>
            <span className="font-semibold text-slate-900">GlobalVox AI Screening</span>
          </div>
          <nav className="flex gap-1">
            <NavItem to="/campaigns">Campaigns</NavItem>
            <NavItem to="/candidates">Candidates</NavItem>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<CampaignsPage />} />
          <Route path="/campaigns" element={<CampaignsPage />} />
          <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
          <Route path="/candidates" element={<CandidatesPage />} />
          <Route path="/screenings/:id" element={<ScreeningDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}
