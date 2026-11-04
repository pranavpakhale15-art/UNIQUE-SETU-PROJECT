import React, { useState } from "react";
import { FileText } from "lucide-react";

export default function ServiceThumbnail({ service, className = "" }) {
  const [failedUrl, setFailedUrl] = useState("");
  const imageUrl = service?.thumbnail_url;
  const showImage = Boolean(imageUrl && imageUrl !== failedUrl);
  const altText = service?.thumbnail_alt_text?.en
    || service?.thumbnail?.alt_text?.en
    || service?.name_en
    || "Service";

  return (
    <div className={`relative overflow-hidden bg-gradient-to-br from-primary/10 via-secondary to-accent/10 ${className}`}>
      {showImage ? (
        <img
          src={imageUrl}
          alt={altText}
          loading="lazy"
          decoding="async"
          className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          onError={() => setFailedUrl(imageUrl)}
        />
      ) : (
        <div role="img" aria-label={`${altText} thumbnail unavailable`} className="absolute inset-0 flex items-center justify-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/60 bg-card/80 text-primary shadow-sm">
            <FileText className="h-7 w-7" aria-hidden="true" />
          </div>
        </div>
      )}
    </div>
  );
}
