import React from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../Auth";
import { colores, espacio, radio } from "../theme";
import { Btn, Cargando, Encabezado, Etiqueta, Vacio } from "../ui";
import Pantalla from "../Pantalla";

export default function Actividad({ navigation }) {
  const { usuario, recargar } = useAuth();
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["mis-publicaciones"],
    queryFn: () => api.get("/api/mis-publicaciones"),
    enabled: Boolean(usuario),
  });

  if (!usuario) {
    return (
      <Pantalla>
        <Encabezado titulo="Mi actividad" subtitulo="Entra para ver lo que publicaste" />
        <Vacio
          titulo="Necesitas una cuenta"
          texto="Entra o crea tu cuenta desde Perfil para gestionar tus publicaciones."
          accion={<Btn onPress={() => navigation.navigate("Perfil")}>Ir a Perfil</Btn>}
        />
      </Pantalla>
    );
  }

  const items = Array.isArray(data) ? data : [];

  const cambiarEstado = async (p) => {
    try {
      await api.patch(`/api/publicaciones/${p.id}`, {
        estado: p.estado === "activa" ? "pausada" : "activa",
      });
      qc.invalidateQueries({ queryKey: ["mis-publicaciones"] });
      qc.invalidateQueries({ queryKey: ["lista"] });
    } catch (e) {
      Alert.alert("No se pudo cambiar el estado", e.message);
    }
  };

  const eliminar = (p) => {
    Alert.alert("Eliminar publicación", `¿Eliminar «${p.titulo}»?`, [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Eliminar",
        style: "destructive",
        onPress: async () => {
          try {
            await api.del(`/api/publicaciones/${p.id}`);
            qc.invalidateQueries({ queryKey: ["mis-publicaciones"] });
            qc.invalidateQueries({ queryKey: ["lista"] });
            recargar();
          } catch (e) {
            Alert.alert("No se pudo eliminar", e.message);
          }
        },
      },
    ]);
  };

  return (
    <Pantalla>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: espacio.l, paddingBottom: espacio.xl * 2 }}>
      <Encabezado titulo="Mi actividad" subtitulo="Tus publicaciones y tus números" />

      <View style={estilos.tarjetas}>
        <Metrica valor={usuario.publicaciones} etiqueta="Publicaciones" />
        <Metrica valor={usuario.vistos_recibidos} etiqueta="Vistos buenos" />
        <Metrica valor={usuario.tratos_cerrados} etiqueta="Tratos cerrados" />
      </View>

      <Text style={estilos.seccion}>Mis publicaciones</Text>

      {isLoading ? (
        <Cargando />
      ) : items.length === 0 ? (
        <Vacio
          titulo="Todavía no publicaste"
          texto="Publica un servicio, producto o favor y aparecerá aquí."
          accion={<Btn onPress={() => navigation.navigate("Publicar", { modo: "servicio" })}>Publicar</Btn>}
        />
      ) : (
        items.map((p) => (
          <View key={p.id} style={estilos.fila}>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: "row", gap: 6, marginBottom: 4 }}>
                <Etiqueta tono={p.estado === "activa" ? "neutro" : "aviso"}>{p.estado}</Etiqueta>
                {p.es_emergencia ? <Etiqueta tono="peligro">Emergencia</Etiqueta> : null}
              </View>
              <Text style={estilos.titulo} numberOfLines={2}>
                {p.titulo}
              </Text>
              <Text style={estilos.meta}>
                {p.precio || "A convenir"} · {p.zona} · {p.vistos} vistos
              </Text>
              <View style={estilos.acciones}>
                <Btn variant="secundario" onPress={() => navigation.navigate("Detalle", { id: p.id })}>
                  Ver
                </Btn>
                <Btn
                  variant="secundario"
                  icon="create-outline"
                  onPress={() => navigation.navigate("Publicar", { publicacion: p })}
                >
                  Editar
                </Btn>
                <Btn variant="secundario" onPress={() => cambiarEstado(p)}>
                  {p.estado === "activa" ? "Pausar" : "Activar"}
                </Btn>
                <Btn variant="peligro" onPress={() => eliminar(p)}>
                  Eliminar
                </Btn>
              </View>
            </View>
          </View>
        ))
      )}

      <View style={estilos.notaCaja}>
        <Text style={estilos.notaTitulo}>Próximamente (fase 2)</Text>
        <Text style={estilos.notaTexto}>
          Cotizaciones, tratos con pago y confirmación, mensajes con el vecino y bandeja de
          conversaciones. Hoy esas acciones se coordinan por WhatsApp.
        </Text>
      </View>
      </ScrollView>
    </Pantalla>
  );
}

function Metrica({ valor, etiqueta }) {
  return (
    <View style={estilos.metrica}>
      <Text style={estilos.metricaValor}>{valor ?? 0}</Text>
      <Text style={estilos.metricaEtiqueta}>{etiqueta}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  tarjetas: { flexDirection: "row", gap: espacio.s, marginBottom: espacio.l },
  metrica: {
    flex: 1,
    backgroundColor: colores.superficie,
    borderRadius: radio.m,
    borderWidth: 1,
    borderColor: colores.linea,
    padding: espacio.m,
    alignItems: "center",
  },
  metricaValor: { fontSize: 22, fontWeight: "800", color: colores.marca },
  metricaEtiqueta: { fontSize: 11, color: colores.suave, marginTop: 2, textAlign: "center" },
  seccion: { fontSize: 17, fontWeight: "800", color: colores.tinta, marginBottom: espacio.s },
  fila: {
    backgroundColor: colores.superficie,
    borderRadius: radio.m,
    borderWidth: 1,
    borderColor: colores.linea,
    padding: espacio.m,
    marginBottom: espacio.s,
  },
  titulo: { fontSize: 15, fontWeight: "700", color: colores.tinta },
  meta: { fontSize: 12, color: colores.suave, marginTop: 4 },
  acciones: { flexDirection: "row", gap: espacio.s, marginTop: espacio.m, flexWrap: "wrap" },
  notaCaja: {
    marginTop: espacio.l,
    backgroundColor: colores.fondo,
    borderRadius: radio.m,
    padding: espacio.m,
  },
  notaTitulo: { fontWeight: "800", color: colores.tinta, marginBottom: 4 },
  notaTexto: { fontSize: 13, color: colores.suave, lineHeight: 19 },
});
