import type { ReactNode } from "react";

interface StatusBannerProps {
  tone?: "info" | "success" | "error" | "warning";
  title?: string;
  message: string;
  action?: ReactNode;
}

export function StatusBanner({
  tone = "info",
  title,
  message,
  action,
}: StatusBannerProps) {
  const role = tone === "error" ? "alert" : "status";

  return (
    <section className={`status-banner status-banner--${tone}`} role={role}>
      <div className="status-banner__copy">
        {title ? <strong>{title}</strong> : null}
        <span>{message}</span>
      </div>
      {action ? <div className="status-banner__action">{action}</div> : null}
    </section>
  );
}
