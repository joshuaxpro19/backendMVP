import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);

  const recargar = useCallback(async () => {
    if (!(await getToken())) {
      setUsuario(null);
      setCargando(false);
      return null;
    }
    try {
      const u = await api.get("/api/perfil");
      setUsuario(u);
      return u;
    } catch {
      await setToken("");
      setUsuario(null);
      return null;
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  const entrar = useCallback(async (telefono, password) => {
    const d = await api.post("/api/login", { telefono, password });
    await setToken(d.token);
    const u = await api.get("/api/perfil");
    setUsuario(u);
    return u;
  }, []);

  const registrar = useCallback(
    async (datos) => {
      await api.post("/api/registro", datos);
      return entrar(datos.telefono, datos.password);
    },
    [entrar]
  );

  const salir = useCallback(async () => {
    try {
      await api.post("/api/logout", {});
    } catch {
      // el JWT es stateless: da igual
    }
    await setToken("");
    setUsuario(null);
  }, []);

  const valor = useMemo(
    () => ({
      usuario,
      cargando,
      entrar,
      registrar,
      salir,
      recargar,
      esModerador: usuario?.rol === "moderador" || usuario?.rol === "admin",
      esAdmin: usuario?.rol === "admin",
    }),
    [usuario, cargando, entrar, registrar, salir, recargar]
  );

  return <AuthCtx.Provider value={valor}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
