import { useCallback, useState } from "react";

/**
 * sessionStorage, deliberately, not localStorage: the key should not outlive
 * the browser tab. It is never sent anywhere except this app's own backend,
 * which forwards it to OpenAI and discards it.
 */
const STORAGE_KEY = "smartanalyst:key";

export function useApiKey() {
  const [key, setKeyState] = useState<string>(
    () => sessionStorage.getItem(STORAGE_KEY) ?? "",
  );

  const setKey = useCallback((value: string) => {
    const trimmed = value.trim();
    sessionStorage.setItem(STORAGE_KEY, trimmed);
    setKeyState(trimmed);
  }, []);

  const clear = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    setKeyState("");
  }, []);

  return { key, setKey, clear, hasKey: key.length > 0 };
}
