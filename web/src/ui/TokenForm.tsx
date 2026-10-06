// Access token form, shared by the chat prompt and the settings screen. "Stay signed in"
// starts unchecked: by default the token dies with the tab.

import { useState } from "preact/hooks";
import { useApp } from "../app/context.ts";
import { isRemembered, saveToken } from "../lib/token.ts";
import { Icon } from "./Icon.tsx";

export function TokenForm({ onSaved, idPrefix }: { onSaved: () => void; idPrefix: string }) {
  const { t } = useApp();
  const [value, setValue] = useState("");
  const [remember, setRemember] = useState(isRemembered);
  const [saved, setSaved] = useState(false);

  return (
    <form
      class="token-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (!value.trim()) return;
        saveToken(value, remember);
        setValue("");
        setSaved(true);
        onSaved();
      }}
    >
      <label for={`${idPrefix}-token`}>{t("token.label")}</label>
      <input
        id={`${idPrefix}-token`}
        type="password"
        autocomplete="off"
        spellcheck={false}
        value={value}
        onInput={(event) => {
          setValue(event.currentTarget.value);
          setSaved(false);
        }}
      />
      <div class="check">
        <input
          id={`${idPrefix}-remember`}
          type="checkbox"
          checked={remember}
          aria-describedby={`${idPrefix}-remember-hint`}
          onChange={(event) => setRemember(event.currentTarget.checked)}
        />
        <label for={`${idPrefix}-remember`}>{t("token.remember")}</label>
      </div>
      <p id={`${idPrefix}-remember-hint`} class="hint">
        {t("token.rememberHint")}
      </p>
      <button type="submit" class="button button-primary">
        <Icon name="check" />
        <span>{t("token.save")}</span>
      </button>
      <p class="hint" role="status">
        {saved ? t("token.saved") : ""}
      </p>
    </form>
  );
}
