/**
 * Shared operator-authentication error detection. Previously this heuristic
 * only existed in chat/page.tsx, so every other page that can hit the same
 * gateway-proxied operator-session failure showed a raw/generic error with
 * no recovery action instead of pointing the operator at Settings.
 */
export function isOperatorAuthError(message: string): boolean {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("operator authentication required") ||
    normalized.includes("operator session") ||
    normalized.includes("operator api key not found")
  );
}

export function operatorRecoveryMessage(message: string): string {
  if (isOperatorAuthError(message)) {
    return (
      "Mission Control is unlocked for local operation, but the local runtime rejected the request. " +
      "Restart the app stack and confirm the gateway and orchestrator services are healthy."
    );
  }
  return message;
}
