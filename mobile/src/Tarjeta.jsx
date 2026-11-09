import React from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { fotoUrl, hace } from "./api";
import { colores, espacio, radio, sombra } from "./theme";
import { Etiqueta } from "./ui";

const ETIQUETA_DISTANCIA = (p, zona) => {
  if (p.ubicacion_aproximada && p.zona === zona) return "en tu sector";
  if (p.distancia_km == null) return p.zona || "";
  if (p.distancia_km < 0.05) return "en tu sector";
  if (p.distancia_km < 1) return `a ${Math.round(p.distancia_km * 1000)} m`;
  return `a ${p.distancia_km.toFixed(1).replace(".", ",")} km`;
};

export default function Tarjeta({ p, zona, onPress }) {
  const esFavor = String(p.tipo || "").startsWith("favor");
  const foto = p.fotos && p.fotos.length ? fotoUrl(p.fotos[0]) : null;
  const medio = String(p.medios_pago || "")
    .split(",")
    .filter(Boolean)
    .filter((m) => !(esFavor && m === "intercambio"))[0];

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [estilos.card, sombra, pressed && { opacity: 0.9 }]}
      accessibilityRole="button"
      accessibilityLabel={`Ver detalle de ${p.titulo}`}
    >
      {foto ? (
        <Image source={{ uri: foto }} style={estilos.foto} resizeMode="cover" />
      ) : (
        <View style={estilos.sinFoto}>
          <Ionicons name="storefront-outline" size={34} color={colores.lineaFuerte} />
        </View>
      )}

      <View style={estilos.cuerpo}>
        <View style={estilos.cabecera}>
          <Text style={estilos.categoria} numberOfLines={1}>
            {(p.categoria || "").toUpperCase()}
          </Text>
          {p.es_emergencia ? (
            <Etiqueta tono="peligro">Emergencia</Etiqueta>
          ) : esFavor ? (
            <Etiqueta tono={p.tipo === "favor_solicitado" ? "aviso" : "neutro"}>
              {p.tipo === "favor_solicitado" ? "Necesito" : "Ofrezco"}
            </Etiqueta>
          ) : p.origen === "scraping" ? (
            <Etiqueta tono="facebook">Facebook</Etiqueta>
          ) : null}
        </View>

        <Text style={estilos.titulo} numberOfLines={2}>
          {p.titulo}
        </Text>

        <View style={estilos.meta}>
          <Ionicons name="location-outline" size={13} color={colores.suave} />
          <Text style={estilos.metaTexto} numberOfLines={1}>
            {ETIQUETA_DISTANCIA(p, zona)}
          </Text>
        </View>

        <View style={estilos.pie}>
          <Text style={estilos.precio} numberOfLines={1}>
            {p.precio || (esFavor ? "Gratis / intercambio" : "A convenir")}
          </Text>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            {p.vistos > 0 ? (
              <>
                <Ionicons name="thumbs-up-outline" size={13} color={colores.suave} />
                <Text style={estilos.vistos}>{p.vistos}</Text>
              </>
            ) : null}
            <Text style={estilos.hace}>{hace(p.creado)}</Text>
          </View>
        </View>

        {medio || p.avaladores?.length ? (
          <View style={estilos.extra}>
            {medio ? <Etiqueta>{medio}</Etiqueta> : null}
            {p.avaladores?.length ? (
              <Etiqueta tono="aviso">Avalado por {p.avaladores[0]?.nombre}</Etiqueta>
            ) : null}
          </View>
        ) : null}
      </View>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  card: {
    backgroundColor: colores.superficie,
    borderRadius: radio.m,
    marginBottom: espacio.m,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colores.linea,
  },
  foto: { width: "100%", height: 150, backgroundColor: colores.fondo2 },
  sinFoto: {
    width: "100%",
    height: 96,
    backgroundColor: colores.fondo2,
    alignItems: "center",
    justifyContent: "center",
  },
  cuerpo: { padding: espacio.m },
  cabecera: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  categoria: { fontSize: 11, fontWeight: "800", color: colores.suave, flex: 1 },
  titulo: { fontSize: 17, fontWeight: "700", color: colores.tinta, marginTop: 6 },
  meta: { flexDirection: "row", alignItems: "center", marginTop: 6 },
  metaTexto: { fontSize: 12, color: colores.suave, marginLeft: 3, flex: 1 },
  pie: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: espacio.s,
    borderTopWidth: 1,
    borderTopColor: colores.linea,
    paddingTop: espacio.s,
  },
  precio: { fontSize: 15, fontWeight: "800", color: colores.marca, flex: 1 },
  vistos: { fontSize: 12, color: colores.suave, marginLeft: 3, marginRight: 8 },
  hace: { fontSize: 11, color: colores.suave },
  extra: { flexDirection: "row", gap: 6, marginTop: espacio.s, flexWrap: "wrap" },
});
