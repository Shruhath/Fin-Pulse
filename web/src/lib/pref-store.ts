import { useCallback, useSyncExternalStore } from "react";

/** A boolean preference kept in localStorage (per browser, never sent anywhere); false when storage is unavailable. */
export function useBooleanPref(key: string, initial = false): [boolean, (value: boolean) => void] {
  const subscribe = useCallback((notify: () => void) => {
    window.addEventListener("storage", notify);
    window.addEventListener(`pref:${key}`, notify);
    return () => {
      window.removeEventListener("storage", notify);
      window.removeEventListener(`pref:${key}`, notify);
    };
  }, [key]);
  const read = useCallback(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored === null ? initial : stored === "1";
    } catch {
      return initial;
    }
  }, [key, initial]);
  const value = useSyncExternalStore(subscribe, read, () => initial);
  const write = useCallback(
    (next: boolean) => {
      try {
        localStorage.setItem(key, next ? "1" : "0");
      } catch {
        /* storage unavailable: the choice lasts only until reload */
      }
      window.dispatchEvent(new Event(`pref:${key}`));
    },
    [key],
  );
  return [value, write];
}
