import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { logout } from "../api/endpoints/auth";
import { queryClient } from "../lib/queryClient";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
  }`;

export function AppLayout() {
  const { user } = useAuth();

  async function handleLogout() {
    await logout();
    queryClient.setQueryData(["auth", "me"], null);
    window.location.href = "/login";
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="text-lg font-semibold">Moneyman</span>
            <nav className="flex gap-1">
              <NavLink to="/" end className={navLinkClass}>
                Dashboard
              </NavLink>
              <NavLink to="/transactions" className={navLinkClass}>
                Transactions
              </NavLink>
              <NavLink to="/review" className={navLinkClass}>
                Review Queue
              </NavLink>
              <NavLink to="/settings" className={navLinkClass}>
                Settings
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {user && <span className="text-sm text-gray-600">{user.email}</span>}
            <button
              onClick={handleLogout}
              className="text-sm text-gray-500 hover:text-gray-800"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
