import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Cliente del contrato `/api/*` de backendMVP (ver front/API-CONTRATO.md).
 *
 * La URL se configura con EXPO_PUBLIC_API_URL (por ejemplo el túnel de
 * Cloudflare del backend). En Expo, las variables EXPO_PUBLIC_* se inyectan
 * al empaquetar, así que hay que reiniciar Metro después de cambiarlas.
 */
export const API_URL = (process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000").replace(
  /\/+$/,
  ""
);

/** true si la app apunta a la propia máquina (no sirve desde un teléfono). */
export const API_LOCAL = /localhost|127\.0\.0\.1/.test(API_URL);

const TOKEN_KEY = "vecinal-token";
let tokenCache = null;

export async function getToken() {
  if (tokenCache !== null) return tokenCache;
  tokenCache = (await AsyncStorage.getItem(TOKEN_KEY)) || "";
  return tokenCache;
}

export async function setToken(t) {
  tokenCache = t || "";
  if (t) await AsyncStorage.setItem(TOKEN_KEY, t);
  else await AsyncStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const t = await getToken();
  if (t) headers.Authorization = `Bearer ${t}`;

  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Sin conexión con el servidor", 0);
  }

  const texto = await res.text();
  let data = null;
  try {
    data = texto ? JSON.parse(texto) : null;
  } catch {
    data = { detail: texto };
  }

  if (!res.ok) {
    // Cloudflare devuelve HTML cuando el túnel (quick tunnel) está caído o cambió.
    if (res.status === 530 || /trycloudflare|cloudflare|error code/i.test(texto)) {
      throw new ApiError(
        "El túnel del backend está caído o cambió de URL. Reinicia el túnel y Expo con --clear.",
        res.status
      );
    }
    const detalle = data && (data.detail || data.mensaje);
    const mensaje =
      typeof detalle === "string" && detalle.length <= 200 ? detalle : `Error ${res.status}`;
    if (res.status === 401) await setToken("");
    throw new ApiError(mensaje, res.status);
  }
  return data;
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: "POST", body }),
  put: (p, body) => request(p, { method: "PUT", body }),
  patch: (p, body) => request(p, { method: "PATCH", body }),
  del: (p) => request(p, { method: "DELETE" }),
};

/** Construye query strings sin depender de URLSearchParams. */
export function qs(params) {
  const partes = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`);
  return partes.length ? `?${partes.join("&")}` : "";
}

/** Las fotos llegan como rutas relativas (/fotos/...). */
export const fotoUrl = (ruta) => (ruta ? `${API_URL}${ruta}` : null);

/** 1767000000 (segundos Unix) -> "hace 2 h" */
export function hace(segundos) {
  if (!segundos) return "";
  const dif = Math.max(0, Math.floor(Date.now() / 1000 - segundos));
  if (dif < 60) return "ahora";
  if (dif < 3600) return `hace ${Math.floor(dif / 60)} min`;
  if (dif < 86400) return `hace ${Math.floor(dif / 3600)} h`;
  if (dif < 604800) return `hace ${Math.floor(dif / 86400)} d`;
  return new Date(segundos * 1000).toLocaleDateString("es-PE");
}
