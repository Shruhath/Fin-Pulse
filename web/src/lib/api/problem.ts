/** The API's own explanation of a refusal (FastAPI sends it as `detail`), else the bare status. */
export async function problem(res: Response): Promise<string> {
  try {
    const { detail } = (await res.json()) as { detail?: unknown };
    if (typeof detail === "string") return detail;
  } catch {
    /* not JSON */
  }
  return `The API answered ${res.status}.`;
}
