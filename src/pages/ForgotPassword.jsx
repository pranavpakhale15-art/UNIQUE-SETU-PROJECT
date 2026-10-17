import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Phone, ArrowLeft, Loader2 } from "lucide-react";
import AuthLayout from "@/components/AuthLayout";
import { requestPasswordReset, normalizeMobileNumber } from "@/api/backendClient";

export default function ForgotPassword() {
  const [mobile, setMobile] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const cleanedMobile = normalizeMobileNumber(mobile);
    if (cleanedMobile.length !== 10) {
      setError("Enter a valid 10-digit mobile number.");
      return;
    }
    setLoading(true);
    try {
      await requestPasswordReset(cleanedMobile);
      setSent(true);
    } catch (requestError) {
      setError(requestError.message || "Unable to request password recovery.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      icon={Phone}
      title="Reset password"
      subtitle="Password recovery is not yet available"
      footer={
        <Link to="/login" className="text-primary font-medium hover:underline">
          <ArrowLeft className="w-3 h-3 inline mr-1" />Back to log in
        </Link>
      }
    >
      {sent ? (
        <p className="text-sm text-foreground text-center">
          If an account exists with that mobile number, recovery guidance will become available once a verified recovery channel is configured.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <div role="alert" className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>}
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
          <Button type="submit" className="w-full h-12 font-medium" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Sending...
              </>
            ) : (
              "Send reset link"
            )}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
