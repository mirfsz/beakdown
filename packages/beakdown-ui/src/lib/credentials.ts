// Read once: React Strict Mode may invoke state initializers twice.
let credentials: { id: string | null; token: string | null } | undefined;
export function credentialsForTab() {
  if (credentials) return credentials;
  const hash = new URLSearchParams(location.hash.slice(1));
  const id = hash.get("session"),
    token = hash.get("token");
  if (id && token) {
    credentials = { id, token };
    sessionStorage.setItem("beakdown.session", JSON.stringify(credentials));
    history.replaceState(null, "", location.pathname);
  } else {
    try {
      credentials = JSON.parse(
        sessionStorage.getItem("beakdown.session") || "null",
      ) ?? { id: null, token: null };
    } catch {
      credentials = { id: null, token: null };
    }
  }
  return credentials!;
}
