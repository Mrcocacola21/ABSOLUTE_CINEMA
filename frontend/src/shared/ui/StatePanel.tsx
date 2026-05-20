import type { ReactNode } from "react";

interface StatePanelProps {
  title: string;
  message: string;
  tone?: "loading" | "empty" | "error";
  action?: ReactNode;
}

export function StatePanel({
  title,
  message,
  tone = "empty",
  action,
}: StatePanelProps) {
  const role = tone === "error" ? "alert" : "status";
  const ariaLive = tone === "error" ? "assertive" : "polite";

  return (
    <section
      className={`panel state-panel state-panel--${tone}`}
      role={role}
      aria-live={ariaLive}
      aria-busy={tone === "loading" ? true : undefined}
    >
      <div className="state-panel__visual" aria-hidden="true">
        {tone === "loading" ? (
          <div className="state-panel__loader">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <span className="state-panel__mark" />
        )}
      </div>
      <div className="state-panel__copy">
        <h2 className="section-title">{title}</h2>
        <p className="muted">{message}</p>
      </div>
      {action ? <div className="actions-row">{action}</div> : null}
    </section>
  );
}
