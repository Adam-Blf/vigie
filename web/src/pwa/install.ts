// Install prompt plumbing. The browser fires beforeinstallprompt once and early, so the
// listener is attached at start-up and the event is kept until someone asks to install.

import { useEffect, useState } from "preact/hooks";

interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

interface InstallState {
  available: boolean;
  installed: boolean;
}

let deferred: InstallPromptEvent | null = null;
let state: InstallState = { available: false, installed: false };
const listeners = new Set<(next: InstallState) => void>();

function publish(next: InstallState): void {
  state = next;
  for (const listener of listeners) listener(state);
}

export function watchInstallPrompt(): void {
  state = { available: false, installed: window.matchMedia("(display-mode: standalone)").matches };
  window.addEventListener("beforeinstallprompt", (event) => {
    // The default mini-infobar is replaced by Vigie's own discreet banner.
    event.preventDefault();
    deferred = event as InstallPromptEvent;
    publish({ ...state, available: true });
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    publish({ available: false, installed: true });
  });
}

export async function promptInstall(): Promise<boolean> {
  if (!deferred) return false;
  const event = deferred;
  deferred = null;
  await event.prompt();
  const choice = await event.userChoice;
  publish({ ...state, available: false });
  return choice.outcome === "accepted";
}

export function useInstall(): InstallState {
  const [current, setCurrent] = useState(state);
  useEffect(() => {
    listeners.add(setCurrent);
    setCurrent(state);
    return () => {
      listeners.delete(setCurrent);
    };
  }, []);
  return current;
}

// The banner shows once in the device's lifetime, after the third question.
export const INSTALL_AFTER_QUESTIONS = 3;

export function shouldOfferInstall(asked: number, alreadyOffered: boolean, available: boolean): boolean {
  return available && !alreadyOffered && asked >= INSTALL_AFTER_QUESTIONS;
}
