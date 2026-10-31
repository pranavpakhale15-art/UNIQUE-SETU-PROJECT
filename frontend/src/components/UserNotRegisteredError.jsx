import React from "react";

export default function UserNotRegisteredError() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="max-w-md w-full rounded-xl bg-white p-8 shadow text-center">
        <h1 className="text-2xl font-semibold text-slate-900 mb-2">
          Access Restricted
        </h1>
        <p className="text-slate-600 mb-6">
          Your account isn't registered for this application. Please contact
          the administrator to request access.
        </p>
        <a href="/" className="text-blue-600 hover:underline">
          Back to home
        </a>
      </div>
    </div>
  );
}