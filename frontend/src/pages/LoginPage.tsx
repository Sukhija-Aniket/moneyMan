import { Navigate } from "react-router-dom";
import { googleLoginUrl } from "../api/endpoints/auth";
import { useAuth } from "../hooks/useAuth";

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-500">
        Loading...
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-6 bg-gray-50">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">Moneyman</h1>
        <p className="mt-2 text-gray-500">
          Track spending across every bank and card email, automatically.
        </p>
      </div>
      <a
        href={googleLoginUrl}
        className="flex items-center gap-2 rounded-md bg-gray-900 px-5 py-3 text-sm font-medium text-white hover:bg-gray-800"
      >
        Sign in with Google
      </a>
    </div>
  );
}
