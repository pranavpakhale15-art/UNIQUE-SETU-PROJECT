import React from "react";
import { useLang } from "@/lib/i18n/LanguageContext";

// Literal class map so Tailwind keeps every variant.
const STATUS_STYLES = {
  draft: "bg-muted text-muted-foreground",
  submitted: "bg-blue-100 text-blue-700",
  received_by_shop: "bg-blue-100 text-blue-700",
  under_review: "bg-amber-100 text-amber-700",
  documents_incomplete: "bg-orange-100 text-orange-700",
  correction_requested: "bg-orange-100 text-orange-700",
  ready_for_processing: "bg-teal-100 text-teal-700",
  in_progress: "bg-indigo-100 text-indigo-700",
  submitted_to_authority: "bg-indigo-100 text-indigo-700",
  awaiting_authority_decision: "bg-purple-100 text-purple-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  completed: "bg-green-100 text-green-700",
  rejected_by_shop: "bg-red-100 text-red-700",
  cancelled: "bg-gray-200 text-gray-600",
};

const STATUS_KEYS = {
  "Draft": "draft",
  "Submitted by Customer": "submitted",
  "Received by Shop": "received_by_shop",
  "Documents Under Review": "under_review",
  "Documents Incomplete": "documents_incomplete",
  "Correction Requested": "correction_requested",
  "Ready for Processing": "ready_for_processing",
  "In Progress": "in_progress",
  "Submitted to Government Authority": "submitted_to_authority",
  "Awaiting Government Decision": "awaiting_authority_decision",
  "Approved by Authority": "approved",
  "Rejected by Authority": "rejected",
  "Completed by Shop": "completed",
  "Rejected by Shop": "rejected_by_shop",
  "Cancelled": "cancelled",
};

export function getStatusTranslationKey(status) {
  return STATUS_KEYS[status] || status;
}

export default function StatusBadge({ status }) {
  const { t } = useLang();
  const key = getStatusTranslationKey(status);
  const cls = STATUS_STYLES[key] || "bg-muted text-muted-foreground";
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${cls}`}>
      {t(`status.${key}`) || status}
    </span>
  );
}