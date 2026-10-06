// Application shell: skip link, header, the permanent AI disclosure, the routed screen
// and the footer with the EUR-Lex source.

import { useEffect, useMemo, useState } from "preact/hooks";
import type { ApiClient, AskResponse, RuntimeConfig } from "../api/types.ts";
import { ChatScreen } from "../chat/ChatScreen.tsx";
import type { MessageKey } from "../i18n/fr.ts";
import { translate, type Locale, type Vars } from "../i18n/translate.ts";
import { KEYS, writeItem } from "../lib/storage.ts";
import { applyTheme, readThemeChoice, type ThemeChoice } from "../lib/theme.ts";
import { PwaBanners } from "../pwa/PwaBanners.tsx";
import { AboutScreen, LegalScreen, PrivacyScreen } from "../screens/InfoScreens.tsx";
import { SettingsScreen } from "../screens/SettingsScreen.tsx";
import { NotFoundScreen, OfflineScreen, ServerErrorScreen } from "../screens/StatusScreens.tsx";
import { UsageScreen } from "../screens/UsageScreen.tsx";
import { AppContext, type AppState, type ServerInfo } from "./context.ts";
import { Footer, Header } from "./Chrome.tsx";
import { routeFor, usePathname, type RouteName } from "./routes.ts";
import { useOnline } from "./useEnvironment.ts";

interface AppProps {
  config: RuntimeConfig;
  client: ApiClient;
  demo: boolean;
  initialLocale: Locale;
}

function Screen({ route, online }: { route: RouteName; online: boolean }) {
  switch (route) {
    case "chat":
      return online ? <ChatScreen /> : <OfflineScreen />;
    case "settings":
      return <SettingsScreen />;
    case "usage":
      return <UsageScreen />;
    case "about":
      return <AboutScreen />;
    case "legal":
      return <LegalScreen />;
    case "privacy":
      return <PrivacyScreen />;
    case "offline":
      return <OfflineScreen />;
    case "error":
      return <ServerErrorScreen />;
    default:
      return <NotFoundScreen />;
  }
}

export function App({ config, client, demo, initialLocale }: AppProps) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const [theme, setThemeState] = useState<ThemeChoice>(readThemeChoice);
  const [server, setServer] = useState<ServerInfo | null>(null);
  const online = useOnline();
  const route = routeFor(usePathname());

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  // Each screen gets its own document title, which screen readers announce on navigation.
  useEffect(() => {
    const titles: Partial<Record<RouteName, MessageKey>> = {
      settings: "settings.title",
      usage: "usage.title",
      about: "about.title",
      legal: "legal.title",
      privacy: "privacy.title",
      offline: "offline.title",
      error: "serverError.title",
      notFound: "notFound.title",
    };
    const key = titles[route];
    document.title = key ? `${translate(locale, key)} | Vigie` : "Vigie";
  }, [route, locale]);

  const state = useMemo<AppState>(
    () => ({
      locale,
      setLocale: (next) => {
        writeItem("local", KEYS.locale, next);
        setLocaleState(next);
      },
      t: (key: MessageKey, vars?: Vars) => translate(locale, key, vars),
      theme,
      setTheme: (next) => {
        applyTheme(next);
        setThemeState(next);
      },
      client,
      config,
      demo,
      online,
      server,
      noteAnswer: (response: AskResponse) =>
        setServer({ appVersion: response.app_version, model: response.model }),
    }),
    [locale, theme, client, config, demo, online, server],
  );

  return (
    <AppContext.Provider value={state}>
      <a class="skip-link" href="#main">
        {state.t("skip.link")}
      </a>
      <Header route={route} />
      <p class="ai-banner">{state.t("banner.ai")}</p>
      {demo && <p class="demo-banner">{state.t("demo.banner")}</p>}
      <main id="main" tabIndex={-1} class={`main main-${route}`}>
        <Screen route={route} online={online} />
      </main>
      <Footer />
      <PwaBanners />
    </AppContext.Provider>
  );
}
