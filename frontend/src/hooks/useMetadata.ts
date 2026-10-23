import { useCallback, useEffect, useState } from "react";

import { getHealth, getMetadata } from "../services/api";
import type { HealthResponse, MetadataResponse } from "../types/api";

interface MetadataState {
  metadata: MetadataResponse | null;
  health: HealthResponse | null;
  loading: boolean;
  error: string | null;
}

export function useMetadata() {
  const [state, setState] = useState<MetadataState>({
    metadata: null,
    health: null,
    loading: true,
    error: null,
  });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState((previous) => ({ ...previous, loading: true, error: null }));
    Promise.allSettled([getMetadata(controller.signal), getHealth(controller.signal)])
      .then(([metadataResult, healthResult]) => {
        if (controller.signal.aborted) return;
        if (metadataResult.status === "rejected") {
          const reason = metadataResult.reason as unknown;
          setState({
            metadata: null,
            health: null,
            loading: false,
            error:
              reason instanceof Error
                ? reason.message
                : "Service metadata could not be loaded.",
          });
          return;
        }
        setState({
          metadata: metadataResult.value,
          health: healthResult.status === "fulfilled" ? healthResult.value : null,
          loading: false,
          error: null,
        });
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setState((previous) => ({
          ...previous,
          loading: false,
          error: "Service metadata could not be loaded.",
        }));
      });
    return () => controller.abort();
  }, [nonce]);

  const retry = useCallback(() => setNonce((value) => value + 1), []);
  return { ...state, retry };
}
