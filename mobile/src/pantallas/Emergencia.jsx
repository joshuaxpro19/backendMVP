import React from "react";
import { Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Ionicons from "@expo/vector-icons/Ionicons";
import { api, qs } from "../api";
import { useAuth } from "../Auth";
import { useZona } from "../Zona";
import { colores, espacio, radio, sombra } from "../theme";
import { Btn, Cargando, Encabezado, Etiqueta, Vacio } from "../ui";
import Tarjeta from "../Tarjeta";
import Pantalla from "../Pantalla";

export default function Emergencia({ navigation }) {
  const { zona, ref } = useZona();
  const { usuario, esModerador } = useAuth();
  const qc = useQueryClient();

  const { data: tablero } = useQuery({
    queryKey: ["emergencia"],
    queryFn: () => api.get("/api/emergencia"),
    refetchInterval: 60000,
  });
  const { data: dir } = useQuery({
    queryKey: ["directorio"],
    queryFn: () => api.get("/api/emergencia/directorio"),
  });
  const { data: recursos, isLoading, refetch } = useQuery({
    queryKey: ["recursos", zona],
    queryFn: () =>
      api.get(
        `/api/publicaciones${qs({ emergencia: "true", limit: 20, zona, lat: ref[0], lng: ref[1] })}`
      ),
  });

  const activo = Boolean(tablero?.activo);

  const alternar = async () => {
    try {
      await api.post("/api/emergencia/activar", {
        activo: !activo,
        motivo: !activo ? "Activado por moderación" : "Desactivado",
      });
      qc.invalidateQueries({ queryKey: ["emergencia"] });
    } catch (e) {
      Alert.alert("No se pudo cambiar el tablero", e.message);
    }
  };

  const directorio = dir?.items || [];
  const items = recursos?.items || [];

  return (
    <Pantalla>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: espacio.l, paddingBottom: espacio.xl * 2 }}
      >
      <Encabezado
        titulo="Emergencia"
        subtitulo="No es un canal oficial: llama a los números si hay riesgo"
        accion={
          <Btn
            icon="add"
            variant="peligro"
            onPress={() => navigation.navigate("Publicar", { modo: "emergencia" })}
          >
            Reportar
          </Btn>
        }
      />

      <View style={[estilos.tablero, activo && estilos.tableroOn]}>
        <Ionicons
          name={activo ? "warning" : "shield-checkmark-outline"}
          size={26}
          color={activo ? "#fff" : colores.marca}
        />
        <View style={{ flex: 1 }}>
          <Text style={[estilos.tableroTitulo, activo && { color: "#fff" }]}>
            {activo ? "Tablero activo" : "Sin emergencia declarada"}
          </Text>
          <Text style={[estilos.tableroTexto, activo && { color: "#fff" }]}>
            {activo
              ? `Activado ${tablero?.motivo ? `por ${tablero.motivo}` : "por moderación"}.`
              : "Los recursos siguen visibles, sin alerta general."}
          </Text>
        </View>
        {esModerador ? (
          <Btn variant="peligro" onPress={alternar}>
            {activo ? "Desactivar" : "Activar"}
          </Btn>
        ) : null}
      </View>

      <Text style={estilos.seccion}>Números de ayuda</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: espacio.m }}>
        {directorio.map((d) => (
          <Pressable
            key={d.id}
            onPress={() => Linking.openURL(`tel:${d.telefono}`)}
            style={[estilos.dir, sombra]}
          >
            <Ionicons name="call-outline" size={18} color={colores.marca} />
            <Text style={estilos.dirNombre} numberOfLines={1}>
              {d.nombre}
            </Text>
            <Text style={estilos.dirTel}>{d.telefono}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <Text style={estilos.seccion}>Recursos en {zona}</Text>

      {isLoading ? (
        <Cargando />
      ) : items.length === 0 ? (
        <Vacio
          titulo="Sin recursos reportados"
          texto="Cuando un vecino publique una necesidad aparecerá aquí."
          accion={
            <Btn variant="peligro" onPress={() => navigation.navigate("Publicar", { modo: "emergencia" })}>
              Reportar necesidad
            </Btn>
          }
        />
      ) : (
        items.map((p) => (
          <Tarjeta
            key={p.id}
            p={p}
            zona={zona}
            onPress={() => navigation.navigate("Detalle", { id: p.id })}
          />
        ))
      )}
      </ScrollView>
    </Pantalla>
  );
}

const estilos = StyleSheet.create({
  tablero: {
    flexDirection: "row",
    alignItems: "center",
    gap: espacio.m,
    backgroundColor: colores.fondo2,
    borderRadius: radio.m,
    padding: espacio.m,
    marginBottom: espacio.l,
  },
  tableroOn: { backgroundColor: colores.peligro },
  tableroTitulo: { fontSize: 15, fontWeight: "800", color: colores.tinta },
  tableroTexto: { fontSize: 12, color: colores.suave, marginTop: 2 },
  seccion: { fontSize: 17, fontWeight: "800", color: colores.tinta, marginBottom: espacio.s },
  dir: {
    width: 150,
    backgroundColor: colores.superficie,
    borderRadius: radio.m,
    padding: espacio.m,
    marginRight: espacio.s,
    borderWidth: 1,
    borderColor: colores.linea,
  },
  dirNombre: { fontSize: 13, fontWeight: "700", color: colores.tinta, marginTop: 6 },
  dirTel: { fontSize: 18, fontWeight: "800", color: colores.marca, marginTop: 2 },
});
