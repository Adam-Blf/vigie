// My usage: numbers from GET /v1/usage/me, with a progress bar that also says its value.

import { useEffect, useState } from "preact/hooks";
import { ApiError } from "../api/errors.ts";
import type { UsageResponse } from "../api/types.ts";
import { useApp } from "../app/context.ts";
import { onLinkClick, ROUTES } from "../app/routes.ts";
import { getToken } from "../lib/token.ts";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; usage: UsageResponse }
  | { kind: "needToken" }
  | { kind: "failed"; error: ApiError };

export function UsageScreen() {
  const { t, client, demo, locale } = useApp();
  const [load, setLoad] = useState<Load>(() =>
    demo || getToken() ? { kind: "loading" } : { kind: "needToken" },
  );

  useEffect(() => {
    if (load.kind !== "loading") return undefined;
    const controller = new AbortController();
    client.usage(controller.signal).then(
      (usage) => setLoad({ kind: "ready", usage }),
      (error: unknown) => {
        const apiError = error instanceof ApiError ? error : new ApiError("network", String(error));
        if (apiError.kind === "aborted") return;
        setLoad(apiError.kind === "unauthorized" ? { kind: "needToken" } : { kind: "failed", error: apiError });
      },
    );
    return () => controller.abort();
  }, [load.kind]);

  const number = new Intl.NumberFormat(locale);
  return (
    <article class="doc usage">
      <h1>{t("usage.title")}</h1>
      {demo && <p class="hint">{t("usage.demo")}</p>}
      {load.kind === "loading" && <p role="status">{t("usage.loading")}</p>}
      {load.kind === "needToken" && (
        <p>
          {t("usage.needToken")}{" "}
          <a href={ROUTES.settings} onClick={(e) => onLinkClick(e, ROUTES.settings)}>
            {t("token.goSettings")}
          </a>
        </p>
      )}
      {load.kind === "failed" && (
        <p role="alert">{load.error.kind === "network" ? t("error.network") : t("error.server")}</p>
      )}
      {load.kind === "ready" && (
        <dl class="usage-grid">
          <div>
            <dt>{t("usage.today")}</dt>
            <dd>
              {t("usage.quota", {
                used: number.format(load.usage.requests_today),
                quota: number.format(load.usage.daily_quota),
              })}
              <progress max={load.usage.daily_quota} value={load.usage.requests_today}>
                {number.format(load.usage.requests_today)}
              </progress>
            </dd>
          </div>
          <div>
            <dt>{t("usage.total")}</dt>
            <dd>{number.format(load.usage.requests)}</dd>
          </div>
          <div>
            <dt>{t("usage.blocked")}</dt>
            <dd>{number.format(load.usage.blocked)}</dd>
          </div>
          <div>
            <dt>{t("usage.refused")}</dt>
            <dd>{number.format(load.usage.refused)}</dd>
          </div>
        </dl>
      )}
    </article>
  );
}
