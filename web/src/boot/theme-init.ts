// Runs as a classic blocking script in <head>, before the first paint, so a person who
// forced the dark theme never sees a white flash. Served as its own file because the
// CSP forbids inline scripts. It stays import-free: it is compiled alone.

(() => {
  try {
    const theme = window.localStorage.getItem("vigie.theme");
    if (theme === "light" || theme === "dark") {
      document.documentElement.dataset.theme = theme;
    }
    const locale = window.localStorage.getItem("vigie.locale");
    if (locale === "fr" || locale === "en") {
      document.documentElement.lang = locale;
    }
  } catch {
    // Blocked storage simply means the system preference applies.
  }
})();
