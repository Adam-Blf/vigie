// Settings: token, language, theme, installation, versions, local history.

import { useState } from "preact/hooks";
import { useApp } from "../app/context.ts";
import { clearHistory } from "../chat/turns.ts";
import { LOCALES } from "../i18n/translate.ts";
import { THEME_CHOICES } from "../lib/theme.ts";
import { clearToken, getToken } from "../lib/token.ts";
import { promptInstall, useInstall } from "../pwa/install.ts";
import { Icon } from "../ui/Icon.tsx";
import { TokenForm } from "../ui/TokenForm.tsx";

export function SettingsScreen() {
  const app = useApp();
  const { t } = app;
  const install = useInstall();
  const [hasToken, setHasToken] = useState(() => getToken() !== null);
  const [notice, setNotice] = useState("");

  return (
    <article class="doc settings">
      <h1>{t("settings.title")}</h1>

      <section aria-labelledby="settings-token">
        <h2 id="settings-token">{t("token.title")}</h2>
        <TokenForm idPrefix="settings" onSaved={() => setHasToken(true)} />
        {hasToken && (
          <button
            type="button"
            class="button button-quiet"
            onClick={() => {
              clearToken();
              clearHistory();
              setHasToken(false);
              setNotice(t("token.loggedOut"));
            }}
          >
            <Icon name="sign-out" />
            <span>{t("token.logout")}</span>
          </button>
        )}
      </section>

      <section aria-labelledby="settings-language">
        <h2 id="settings-language">{t("settings.language")}</h2>
        <fieldset class="segmented">
          <legend class="sr-only">{t("settings.language")}</legend>
          {LOCALES.map((locale) => (
            <label key={locale}>
              <input
                type="radio"
                name="locale"
                value={locale}
                checked={app.locale === locale}
                onChange={() => app.setLocale(locale)}
              />
              <span lang={locale}>{t(`lang.${locale}`)}</span>
            </label>
          ))}
        </fieldset>
      </section>

      <section aria-labelledby="settings-theme">
        <h2 id="settings-theme">{t("settings.theme")}</h2>
        <fieldset class="segmented">
          <legend class="sr-only">{t("settings.theme")}</legend>
          {THEME_CHOICES.map((choice) => (
            <label key={choice}>
              <input
                type="radio"
                name="theme"
                value={choice}
                checked={app.theme === choice}
                onChange={() => app.setTheme(choice)}
              />
              <span>{t(`theme.${choice}`)}</span>
            </label>
          ))}
        </fieldset>
      </section>

      <section aria-labelledby="settings-install">
        <h2 id="settings-install">{t("settings.install")}</h2>
        {install.installed ? (
          <p>{t("settings.install.done")}</p>
        ) : install.available ? (
          <button type="button" class="button button-primary" onClick={() => void promptInstall()}>
            <Icon name="download-simple" />
            <span>{t("settings.install.action")}</span>
          </button>
        ) : (
          <p class="hint">{t("settings.install.unavailable")}</p>
        )}
      </section>

      <section aria-labelledby="settings-version">
        <h2 id="settings-version">{t("settings.version")}</h2>
        <p>{t("settings.version.ui", { version: __APP_VERSION__ })}</p>
        <p>
          {app.server
            ? t("settings.version.api", { version: app.server.appVersion, model: app.server.model })
            : t("settings.version.apiUnknown")}
        </p>
      </section>

      <section aria-labelledby="settings-history">
        <h2 id="settings-history">{t("settings.history")}</h2>
        <button
          type="button"
          class="button button-quiet"
          onClick={() => {
            clearHistory();
            setNotice(t("settings.history.cleared"));
          }}
        >
          <Icon name="trash" />
          <span>{t("settings.history.clear")}</span>
        </button>
      </section>
      <p class="hint" role="status">
        {notice}
      </p>
    </article>
  );
}
