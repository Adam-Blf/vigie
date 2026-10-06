// About, legal notice and privacy: plain documents built from dictionary sections, so
// both languages stay in step and the texts live in one reviewed place.

import { useApp } from "../app/context.ts";
import type { MessageKey } from "../i18n/fr.ts";

type Section = readonly [title: MessageKey | null, body: MessageKey];

function DocScreen({ title, sections }: { title: MessageKey; sections: readonly Section[] }) {
  const { t } = useApp();
  return (
    <article class="doc">
      <h1>{t(title)}</h1>
      {sections.map(([heading, body]) => (
        <section key={body}>
          {heading && <h2>{t(heading)}</h2>}
          <p>{t(body)}</p>
        </section>
      ))}
    </article>
  );
}

export function AboutScreen() {
  const { t } = useApp();
  return (
    <>
      <DocScreen
        title="about.title"
        sections={[
          [null, "about.p1"],
          [null, "about.p2"],
          ["about.ai.title", "about.ai"],
          ["about.sources.title", "about.sources"],
          [null, "about.school"],
        ]}
      />
      <p class="doc doc-version">{t("settings.version.ui", { version: __APP_VERSION__ })}</p>
    </>
  );
}

export function LegalScreen() {
  return (
    <DocScreen
      title="legal.title"
      sections={[
        ["legal.editor.title", "legal.editor"],
        ["legal.director.title", "legal.director"],
        ["legal.contact.title", "legal.contact"],
        ["legal.host.title", "legal.host"],
        ["legal.ip.title", "legal.ip"],
      ]}
    />
  );
}

export function PrivacyScreen() {
  return (
    <DocScreen
      title="privacy.title"
      sections={[
        ["privacy.controllers.title", "privacy.controllers"],
        ["privacy.purposes.title", "privacy.purposes"],
        ["privacy.data.title", "privacy.data"],
        ["privacy.retention.title", "privacy.retention"],
        ["privacy.recipients.title", "privacy.recipients"],
        ["privacy.storage.title", "privacy.storage"],
        ["privacy.rights.title", "privacy.rights"],
      ]}
    />
  );
}
