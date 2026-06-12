import { useAuth } from "@humansignal/core/providers/AuthProvider";

/**
 * True when the current session was minted by the OpenTrain launch bridge.
 * isEmbedded() gates chrome/layout; this gates capability — it keeps holding
 * when the runtime is opened standalone via "Open in new tab".
 */
export function useBridgeSession(): boolean {
  const { user } = useAuth();
  return user?.bridge_session === true;
}
