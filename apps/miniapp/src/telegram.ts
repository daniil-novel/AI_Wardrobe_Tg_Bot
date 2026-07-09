export type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  initData?: string;
  colorScheme?: "light" | "dark";
  themeParams?: Record<string, string>;
  viewportStableHeight?: number;
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
