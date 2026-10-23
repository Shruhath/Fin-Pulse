/**
 * Where the browser finds the API. In a frozen copy (NEXT_PUBLIC_FINPULSE_SNAPSHOT=1, the hosted demonstration)
 * the API is the application's own `/api` routes, which answer from recorded data; otherwise it is the local
 * FastAPI server.
 */
export const FROZEN = process.env.NEXT_PUBLIC_FINPULSE_SNAPSHOT === "1";

export const API = FROZEN ? "" : (process.env.NEXT_PUBLIC_FINPULSE_API_URL ?? "http://127.0.0.1:8000");
