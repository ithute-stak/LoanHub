/**
 * Browser-facing contract for a future installed Wacom STU native connector.
 *
 * Security: never allow arbitrary connector URLs; HTTPS LoanHub may only talk
 * to loopback. The native agent must independently authenticate requests,
 * validate Origin and session authorization, and disable CORS for other sites.
 * A health response does NOT authorize signing or prove a real pad is present.
 */
export type WacomConnectionStatus =
  | { state: "available"; model: string; firmware?: string }
  | { state: "unavailable"; reason: string };

export const WACOM_LOCAL_CONNECTOR = "http://127.0.0.1:8765";

type DeviceHealth = {
  protocol: "loanhub-wacom-v1";
  connected: boolean;
  model?: string;
  firmware?: string;
};

export async function checkWacomConnector(
  fetcher: typeof fetch = fetch,
): Promise<WacomConnectionStatus> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2500);
  try {
    // The native service is not implemented yet. No contract or customer
    // data is transmitted by this diagnostic request.
    const response = await fetcher(`${WACOM_LOCAL_CONNECTOR}/v1/device/status`, {
      method: "GET",
      cache: "no-store",
      credentials: "omit",
      mode: "cors",
      signal: controller.signal,
    });
    if (!response.ok) return { state: "unavailable", reason: "Connector did not respond successfully" };
    const body: unknown = await response.json();
    if (
      typeof body !== "object" || body === null ||
      !("protocol" in body) || body.protocol !== "loanhub-wacom-v1" ||
      !("connected" in body) || body.connected !== true ||
      !("model" in body) || typeof body.model !== "string" || !body.model.trim()
    ) return { state: "unavailable", reason: "No compatible Wacom device reported" };
    const result = body as DeviceHealth;
    return {
      state: "available",
      model: result.model!.slice(0, 100),
      ...(typeof result.firmware === "string" ? { firmware: result.firmware.slice(0, 100) } : {}),
    };
  } catch {
    return { state: "unavailable", reason: "Local Wacom connector unavailable" };
  } finally {
    clearTimeout(timeout);
  }
}
