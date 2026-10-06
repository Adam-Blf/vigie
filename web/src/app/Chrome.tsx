// Header and footer around every screen.

import { nextThemeChoice, type ThemeChoice } from "../lib/theme.ts";
import type { IconName } from "../ui/icon-names.ts";
import { Icon } from "../ui/Icon.tsx";
import { useApp } from "./context.ts";
import { onLinkClick, ROUTES, type RouteName } from "./routes.ts";

const NAV: readonly { route: RouteName; path: string; icon: IconName; label: "nav.chat" | "nav.usage" | "nav.settings" | "nav.about" }[] = [
  { route: "chat", path: ROUTES.chat, icon: "chat-circle-text", label: "nav.chat" },
  { route: "usage", path: ROUTES.usage, icon: "chart-bar", label: "nav.usage" },
  { route: "settings", path: ROUTES.settings, icon: "gear", label: "nav.settings" },
  { route: "about", path: ROUTES.about, icon: "info", label: "nav.about" },
];

const THEME_ICON: Record<ThemeChoice, IconName> = {
  system: "circle-half",
  light: "sun",
  dark: "moon",
};

export function Header({ route }: { route: RouteName }) {
  const { t, theme, setTheme } = useApp();
  return (
    <header class="site-header">
      <a class="brand" href={ROUTES.chat} onClick={(e) => onLinkClick(e, ROUTES.chat)}>
        <img src="/favicon.svg" width="32" height="32" alt="" />
        <span class="brand-name">{t("app.name")}</span>
      </a>
      <nav aria-label={t("nav.label")}>
        <ul class="nav">
          {NAV.map((item) => (
            <li key={item.route}>
              <a
                href={item.path}
                class="nav-link"
                aria-current={route === item.route ? "page" : undefined}
                onClick={(e) => onLinkClick(e, item.path)}
              >
                <Icon name={item.icon} />
                <span class="nav-label">{t(item.label)}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <button
        type="button"
        class="icon-button theme-toggle"
        aria-label={t("theme.toggle", { theme: t(`theme.${theme}`) })}
        onClick={() => setTheme(nextThemeChoice(theme))}
      >
        <Icon name={THEME_ICON[theme]} />
      </button>
    </header>
  );
}

export function Footer() {
  const { t } = useApp();
  const links = [
    { path: ROUTES.legal, label: t("footer.legal") },
    { path: ROUTES.privacy, label: t("footer.privacy") },
    { path: ROUTES.about, label: t("footer.about") },
  ];
  return (
    <footer class="site-footer" aria-label={t("footer.label")}>
      <p>{t("footer.source")}</p>
      <ul class="footer-links">
        {links.map((link) => (
          <li key={link.path}>
            <a href={link.path} onClick={(e) => onLinkClick(e, link.path)}>
              {link.label}
            </a>
          </li>
        ))}
      </ul>
    </footer>
  );
}
