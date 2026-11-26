import { tableFromIPC } from "apache-arrow";
export async function loadArrow(url: string, token: string) {
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Unable to load Arrow preview");
  return tableFromIPC(await response.arrayBuffer());
}
