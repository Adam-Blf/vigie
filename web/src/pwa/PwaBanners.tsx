// "New version available" and "install Vigie" banners. The service worker is registered
// in prompt mode: an update waits for a click, so a half-typed question is never lost.

import { useEffect, useState } from "preact/hooks";
import { useRegisterSW } from "virtual:pwa-register/preact";
import { useApp } from "../app/context.ts";
import { ASKED_EVENT } from "../chat/useChat.ts";
import { KEYS, readItem, writeItem } from "../lib/storage.ts";
import { Icon } from "../ui/Icon.tsx";
import { promptInstall, shouldOfferInstall, useInstall } from "./install.ts";

export function PwaBanners() {
  const { t } = useApp();
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW();
  const install = useInstall();
  const [offerInstall, setOfferInstall] = useState(false);

  useEffect(() => {
    const check = () => {
      const asked = Number(readItem("local", KEYS.questionsAsked) ?? "0");
      const offered = readItem("local", KEYS.installOffered) === "1";
      if (shouldOfferInstall(asked, offered, install.available)) {
        writeItem("local", KEYS.installOffered, "1");
        setOfferInstall(true);
      }
    };
    check();
    window.addEventListener(ASKED_EVENT, check);
    return () => window.removeEventListener(ASKED_EVENT, check);
  }, [install.available]);

  return (
    <div class="banners">
      {needRefresh && (
        <div class="banner" role="status">
          <Icon name="arrow-clockwise" />
          <p>{t("pwa.update")}</p>
          <button type="button" class="button button-primary" onClick={() => void updateServiceWorker(true)}>
            {t("pwa.reload")}
          </button>
          <button type="button" class="button button-quiet" onClick={() => setNeedRefresh(false)}>
            {t("pwa.later")}
          </button>
        </div>
      )}
      {offerInstall && install.available && (
        <div class="banner" role="status">
          <Icon name="download-simple" />
          <p>{t("pwa.install")}</p>
          <button
            type="button"
            class="button button-primary"
            onClick={() => {
              setOfferInstall(false);
              void promptInstall();
            }}
          >
            {t("pwa.installAction")}
          </button>
          <button
            type="button"
            class="icon-button"
            aria-label={t("pwa.dismiss")}
            onClick={() => setOfferInstall(false)}
          >
            <Icon name="x" />
          </button>
        </div>
      )}
    </div>
  );
}
