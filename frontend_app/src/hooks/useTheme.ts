import { useCallback, useEffect, useState } from "react";

import type { Mode } from "../lib/palette";

const STORAGE_KEY = "smartanalyst:theme";

function currentTheme(): Mode {
  const stamped = document.documentElement.dataset.theme;
  return stamped === "dark" ? "dark" : "light";
}

/**
 * Theme state, persisted and stamped on the root element.
 *
 * index.html applies the stored value before first paint, so this hook reads
 * that rather than deciding again and causing a flash.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Mode>(currentTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((previous) => (previous === "dark" ? "light" : "dark"));
  }, []);

  return { theme, toggle };
}
