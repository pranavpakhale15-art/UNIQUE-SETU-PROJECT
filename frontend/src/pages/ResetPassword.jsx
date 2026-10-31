import React from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import AuthLayout from "@/components/AuthLayout";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const resetToken = searchParams.get("token");

  return (
    <AuthLayout
      icon={AlertTriangle}
      title={resetToken ? "Password reset unavailable" : "Invalid reset link"}
      subtitle="Password recovery requires a verified recovery provider"
      footer={
        <Link to="/login" className="text-primary font-medium hover:underline">
          Back to log in
        </Link>
      }
    >
      <p className="text-sm text-foreground text-center">
        {resetToken
          ? "The backend cannot securely verify or use reset links until an SMS or email recovery provider is configured. Contact the service administrator for help."
          : "This link is missing a reset token. Password recovery is not available yet; contact the service administrator for help."}
      </p>
    </AuthLayout>
  );
}
