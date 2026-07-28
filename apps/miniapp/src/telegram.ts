export type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  initData?: string;
  colorScheme?: "light" | "dark";
  themeParams?: Record<string, string>;
  viewportStableHeight?: number;
  isVersionAtLeast?: (version: string) => boolean;
  MainButton?: {
    setText: (text: string) => void;
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
  };
  BackButton?: {
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: "light" | "medium" | "heavy") => void;
    notificationOccurred: (type: "success" | "warning" | "error") => void;
  };
  showConfirm?: (message: string, callback: (confirmed: boolean) => void) => void;
};

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

export function getTelegramWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}

export function getHapticFeedback(
  webApp: TelegramWebApp | undefined = getTelegramWebApp(),
): TelegramWebApp["HapticFeedback"] | undefined {
  return webApp?.isVersionAtLeast?.("6.1") ? webApp.HapticFeedback : undefined;
}

export function confirmDialog(message: string, callback: (confirmed: boolean) => void): void {
  const webApp = getTelegramWebApp();
  if (webApp?.showConfirm) {
    try {
      webApp.showConfirm(message, callback);
      return;
    } catch {
      // Telegram clients below 6.2 (and plain browsers) throw
      // WebAppMethodUnsupported — fall back to the native confirm.
    }
  }
  callback(window.confirm(message));
}
