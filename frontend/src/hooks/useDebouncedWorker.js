import { useCallback, useEffect, useRef, useState } from "react";

export function useDebouncedWorker(worker, delay = 220) {
  const [loading, setLoading] = useState(false);
  const timeoutRef = useRef(null);
  const requestIdRef = useRef(0);

  const scheduleWork = useCallback(
    (payload, transferables = []) => {
      if (!worker) {
        return;
      }

      setLoading(true);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;

      timeoutRef.current = setTimeout(() => {
        worker.postMessage({ ...payload, requestId }, transferables);
      }, delay);
    },
    [worker, delay],
  );

  const clearPendingWork = useCallback(() => {
    setLoading(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return {
    loading,
    scheduleWork,
    clearPendingWork,
    latestRequestIdRef: requestIdRef,
    setLoading,
  };
}
