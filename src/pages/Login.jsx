import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LogIn, Lock, Loader2, Phone } from "lucide-react";
import AuthLayout from "@/components/AuthLayout";
import { safeReturnTo } from "@/lib/authReturnTo";
import { loginWithMobilePassword, normalizeMobileNumber } from "@/api/backendClient";
import { useAuth } from "@/lib/AuthContext";

export default function Login() {
  const { isAuthenticated, user, setAuthenticatedUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [accountType, setAccountType] = useState("customer");
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const returnTo = safeReturnTo();
  const rolePath = user?.role === "customer" ? "/dashboard" : "/workspace";

  useEffect(() => {
    setAccountType("customer");
    setMobile("");
    setPassword("");
    setError("");
    setLoading(false);
  }, [location.key, location.search]);

  useEffect(() => {
    if (isAuthenticated) {
      navigate(returnTo !== "/" ? returnTo : rolePath, { replace: true });
    }
  }, [isAuthenticated, navigate, returnTo, rolePath]);

  if (isAuthenticated) {
    return <div role="status" className="min-h-screen flex items-center justify-center text-muted-foreground">Returning to your account…</div>;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError("");

    const cleanedMobile = normalizeMobileNumber(mobile);
    if (cleanedMobile.length !== 10) {
      setError("Enter a valid 10-digit mobile number");
      return;
    }

    setLoading(true);
    try {
      const result = await loginWithMobilePassword(cleanedMobile, password, accountType);
      if (!result?.user) throw new Error("Login did not return an account profile");
      setAuthenticatedUser(result.user);
      const destination = returnTo !== "/"
        ? returnTo
        : result.user.role === "customer" ? "/dashboard" : "/workspace";
      navigate(destination, { replace: true });
    } catch (err) {
      setError(err.message || "Invalid mobile number or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      icon={LogIn}
      title="Welcome back"
      subtitle="Log in to your account"
      footer={
        <>
          Don't have an account?{" "}
          <Link
            to={"/register" + (returnTo !== "/" ? "?returnTo=" + encodeURIComponent(returnTo) : "")}
            className="text-primary font-medium hover:underline"
          >
            Create one
          </Link>
        </>
      }
    >
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="accountType">Account type</Label>
          <select
            id="accountType"
            value={accountType}
            onChange={(event) => setAccountType(event.target.value)}
            className="h-12 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="customer">Customer</option>
            <option value="owner">Owner</option>
            <option value="admin">Admin</option>
            <option value="staff">Staff</option>
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="mobile">Mobile number</Label>
          <div className="relative">
            <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" aria-hidden="true" />
            <Input
              id="mobile"
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              autoFocus
              placeholder="9876543210"
              value={mobile}
              onChange={(e) => setMobile(e.target.value)}
              className="pl-10 h-12"
              required
            />
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link to="/forgot-password" className="text-xs text-primary hover:underline">
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" aria-hidden="true" />
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="pl-10 h-12"
              required
            />
          </div>
        </div>
        <Button type="submit" className="w-full h-12 font-medium" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Logging in...
            </>
          ) : (
            "Log in"
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}
