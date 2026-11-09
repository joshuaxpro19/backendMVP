import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Location from "expo-location";
import { api } from "./api";
import { useAuth } from "./Auth";

const ZonaCtx = createContext(null);

const ZONA_KEY = "vecinal-zona";
const GPS_KEY = "vecinal-gps";

export function ZonaProvider({ children }) {
  const { usuario } = useAuth();
  const [zonas, setZonas] = useState([]);
  const [zona, setZonaState] = useState("Piura Centro");
  const [gps, setGps] = useState(null);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    (async () => {
      const guardada = await AsyncStorage.getItem(ZONA_KEY);
      if (guardada) setZonaState(guardada);
      const g = await AsyncStorage.getItem(GPS_KEY);
      if (g) {
        try {
          setGps(JSON.parse(g));
        } catch {
          // GPS corrupto: se ignora
        }
      }
      setListo(true);
    })();
  }, []);

  useEffect(() => {
    api
      .get("/api/zonas")
      .then((z) => Array.isArray(z) && setZonas(z))
      .catch(() => {});
  }, []);

  // El sector de la cuenta manda, salvo que la persona lo haya cambiado a mano.
  useEffect(() => {
    if (usuario?.zona) {
      setZonaState(usuario.zona);
      AsyncStorage.setItem(ZONA_KEY, usuario.zona);
    }
  }, [usuario?.zona]);

  const setZona = useCallback(async (nueva) => {
    setZonaState(nueva);
    await AsyncStorage.setItem(ZONA_KEY, nueva);
    setGps(null);
    await AsyncStorage.removeItem(GPS_KEY);
  }, []);

  const usarGPS = useCallback(async () => {
    const permiso = await Location.requestForegroundPermissionsAsync();
    if (permiso.status !== "granted") {
      throw new Error("No pudimos ubicarte. Elige tu sector a mano.");
    }
    const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
    const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
    setGps(coords);
    await AsyncStorage.setItem(GPS_KEY, JSON.stringify(coords));

    if (zonas.length) {
      let mejor = null;
      let mejorDist = Infinity;
      for (const z of zonas) {
        const d = (z.lat - coords.lat) ** 2 + (z.lng - coords.lng) ** 2;
        if (d < mejorDist) {
          mejorDist = d;
          mejor = z;
        }
      }
      if (mejor) {
        setZonaState(mejor.nombre);
        await AsyncStorage.setItem(ZONA_KEY, mejor.nombre);
      }
    }
    return coords;
  }, [zonas]);

  const ref = useMemo(() => {
    if (gps) return [gps.lat, gps.lng];
    const z = zonas.find((x) => x.nombre === zona);
    return z ? [z.lat, z.lng] : [null, null];
  }, [gps, zonas, zona]);

  const valor = useMemo(
    () => ({ zonas, zona, setZona, gps, usarGPS, ref, listo }),
    [zonas, zona, setZona, gps, usarGPS, ref, listo]
  );

  return <ZonaCtx.Provider value={valor}>{children}</ZonaCtx.Provider>;
}

export const useZona = () => useContext(ZonaCtx);
