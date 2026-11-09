import React, { useState } from "react";
import {
  Alert,
  Image,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Ionicons from "@expo/vector-icons/Ionicons";
import { api, fotoUrl, hace } from "./api";
import { useAuth } from "./Auth";
import { colores, espacio, radio } from "./theme";
import { Btn, Cargando, Etiqueta, Vacio } from "./ui";
import Pantalla from "./Pantalla";

const MOTIVOS = ["Parece una estafa", "Datos falsos", "Contenido ofensivo", "Spam"];

export default function Detalle({ route, navigation }) {
  const { id } = route.params;
  const { usuario } = useAuth();
  const qc = useQueryClient();
  const [enviando, setEnviando] = useState(false);
  const [recomendado, setRecomendado] = useState(null);

  const { data: p, isLoading } = useQuery({
    queryKey: ["publicacion", id],
    queryFn: () => api.get(`/api/publicaciones/${id}`),
  });

  if (isLoading)
    return (
      <Pantalla>
        <Cargando texto="Abriendo la publicación…" />
      </Pantalla>
    );
  if (!p) {
    return (
      <Pantalla>
        <Vacio
          titulo="No encontrada"
          texto="La publicación ya no está disponible."
          accion={<Btn onPress={() => navigation.goBack()}>Volver</Btn>}
        />
      </Pantalla>
    );
  }

  const esFavor = String(p.tipo || "").startsWith("favor");
  const esScraping = p.origen === "scraping";
  const esMio = Boolean(p.es_mio);
  const yaRecomende = recomendado === null ? Boolean(p.ya_recomende) : recomendado;
  const fotos = (p.fotos || []).filter(Boolean);

  const hayContacto = Boolean(p.whatsapp || p.telefono);
  const etiquetaContacto = !usuario
    ? "Contactar"
    : p.whatsapp
      ? "Contactar por WhatsApp"
      : p.telefono
        ? "Llamar al vecino"
        : "Sin contacto";

  const contactar = async () => {
    if (!usuario) {
      Alert.alert("Entra para contactar", "Necesitas una cuenta para ver el contacto.");
      navigation.navigate("Tabs", { screen: "Perfil" });
      return;
    }
    if (!hayContacto) {
      Alert.alert("Sin contacto", "Esta publicación no dejó un número para contactar.");
      return;
    }
    setEnviando(true);
    try {
      const texto = encodeURIComponent(`Hola, vi tu publicación en DelBarrio: ${p.titulo}`);
      if (p.whatsapp) {
        await Linking.openURL(`https://wa.me/51${p.whatsapp}?text=${texto}`);
      } else {
        await Linking.openURL(`tel:+51${p.telefono}`);
      }
    } catch {
      Alert.alert("No se pudo abrir", "Revisa que tengas WhatsApp o teléfono disponible.");
    } finally {
      setEnviando(false);
    }
  };

  const recomendar = async () => {
    if (!usuario) {
      Alert.alert("Entra para recomendar", "Necesitas una cuenta para dar un visto bueno.");
      return;
    }
    try {
      if (yaRecomende) {
        // Quitar el visto bueno (toggle)
        const r = await api.del(`/api/vistos?publicacion_id=${p.id}`);
        setRecomendado(false);
        qc.setQueryData(["publicacion", id], { ...p, vistos: r.vistos, ya_recomende: false });
      } else {
        const r = await api.post("/api/vistos", { publicacion_id: p.id, comentario: "" });
        setRecomendado(true);
        qc.setQueryData(["publicacion", id], { ...p, vistos: r.vistos, ya_recomende: true });
      }
      qc.invalidateQueries({ queryKey: ["lista"] });
    } catch (e) {
      Alert.alert("No se pudo actualizar", e.message);
    }
  };

  const reportar = () => {
    if (!usuario) {
      Alert.alert("Entra para reportar", "Necesitas una cuenta para reportar.");
      return;
    }
    Alert.alert("¿Por qué lo reportas?", "", [
      ...MOTIVOS.map((m) => ({
        text: m,
        onPress: async () => {
          try {
            await api.post("/api/reportes", { publicacion_id: p.id, motivo: m });
            Alert.alert("Reporte enviado", "Un moderador lo revisará.");
          } catch (e) {
            Alert.alert("No se pudo reportar", e.message);
          }
        },
      })),
      { text: "Cancelar", style: "cancel" },
    ]);
  };

  return (
    <Pantalla style={{ backgroundColor: colores.superficie }}>
      <ScrollView style={estilos.contenedor} contentContainerStyle={{ paddingBottom: espacio.xl }}>
      <View style={estilos.cabecera}>
        <Pressable onPress={() => navigation.goBack()} hitSlop={12} accessibilityLabel="Cerrar">
          <Ionicons name="close" size={26} color={colores.tinta} />
        </Pressable>
        <Text style={estilos.cabeceraTexto}>{hace(p.creado) || "Recién publicado"}</Text>
      </View>

      {fotos.length ? (
        <Image source={{ uri: fotoUrl(fotos[0]) }} style={estilos.hero} resizeMode="cover" />
      ) : null}

      <View style={estilos.cuerpo}>
        <View style={estilos.filaEtiquetas}>
          <Etiqueta>{(p.categoria || "").toUpperCase()}</Etiqueta>
          {esScraping ? <Etiqueta tono="facebook">Facebook</Etiqueta> : null}
          {p.es_emergencia ? <Etiqueta tono="peligro">Emergencia</Etiqueta> : null}
          {esFavor ? (
            <Etiqueta tono="aviso">
              {p.tipo === "favor_solicitado" ? "Necesito" : "Ofrezco"}
            </Etiqueta>
          ) : null}
          {p.es_mio ? <Etiqueta tono="aviso">Tu publicación</Etiqueta> : null}
        </View>

        <Text style={estilos.titulo}>{p.titulo}</Text>

        <Text style={estilos.precio}>
          {p.precio || (esFavor ? "Gratis / intercambio" : "A convenir")}
        </Text>

        {p.descripcion ? <Text style={estilos.descripcion}>{p.descripcion}</Text> : null}

        <View style={estilos.datos}>
          <Dato icono="person-outline" texto={p.nombre || "Vecino"} />
          <Dato icono="location-outline" texto={p.zona} />
          {p.distancia_km != null ? (
            <Dato
              icono="navigate-outline"
              texto={
                p.distancia_km < 1
                  ? `a ${Math.round(p.distancia_km * 1000)} m`
                  : `a ${p.distancia_km.toFixed(1).replace(".", ",")} km`
              }
            />
          ) : null}
          {p.medios_pago ? <Dato icono="card-outline" texto={p.medios_pago.replace(/,/g, " · ")} /> : null}
          {p.franja_horaria ? <Dato icono="time-outline" texto={p.franja_horaria} /> : null}
          {p.punto_encuentro ? <Dato icono="pin-outline" texto={p.punto_encuentro} /> : null}
          {p.vistos > 0 ? (
            <Dato icono="thumbs-up-outline" texto={`${p.vistos} vecino(s) lo recomiendan`} />
          ) : null}
        </View>

        {p.avaladores?.length ? (
          <View style={estilos.aval}>
            <Ionicons name="shield-checkmark-outline" size={18} color={colores.marca} />
            <Text style={estilos.avalTexto}>
              Avalado por {p.avaladores[0]?.nombre}
              {p.avaladores[0]?.tipo ? ` (${p.avaladores[0].tipo})` : ""}
            </Text>
          </View>
        ) : null}

        <View style={{ marginTop: espacio.l, gap: espacio.s }}>
          <View style={{ flexDirection: "row", gap: espacio.s }}>
            <Btn
              onPress={contactar}
              disabled={enviando || (Boolean(usuario) && !hayContacto)}
              style={{ flex: 1 }}
              icon={p.whatsapp || !usuario ? "logo-whatsapp" : "call-outline"}
            >
              {enviando ? "Abriendo…" : etiquetaContacto}
            </Btn>
            {!esMio && !esScraping ? (
              <Btn
                variant={yaRecomende ? "primary" : "secundario"}
                onPress={recomendar}
                style={{ flex: 1 }}
                icon={yaRecomende ? "thumbs-up" : "thumbs-up-outline"}
              >
                {yaRecomende ? "Recomendado" : "Recomendar"}
              </Btn>
            ) : null}
          </View>

          {esScraping && p.url_origen ? (
            <Btn variant="secundario" icon="open-outline" onPress={() => Linking.openURL(p.url_origen)}>
              Ver publicación en Facebook
            </Btn>
          ) : null}

          {esMio ? (
            <Btn
              variant="secundario"
              icon="create-outline"
              onPress={() => navigation.navigate("Publicar", { publicacion: p })}
            >
              Editar publicación
            </Btn>
          ) : null}

          {!esMio && !esScraping ? (
            <Btn variant="peligro" onPress={reportar} icon="flag-outline">
              Reportar
            </Btn>
          ) : null}

          <Text style={estilos.nota}>
            {esMio
              ? "Esta publicación es tuya. Puedes pausarla o eliminarla desde Actividad."
              : esScraping
                ? "Contenido público de Facebook. Coordina directamente con la persona."
                : "El chat dentro de la app llega en la fase 2. Por ahora se coordina por WhatsApp."}
          </Text>
        </View>
      </View>
      </ScrollView>
    </Pantalla>
  );
}

function Dato({ icono, texto }) {
  return (
    <View style={estilos.dato}>
      <Ionicons name={icono} size={16} color={colores.suave} />
      <Text style={estilos.datoTexto}>{texto}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  contenedor: { flex: 1, backgroundColor: colores.superficie },
  cabecera: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: espacio.l,
  },
  cabeceraTexto: { color: colores.suave, fontSize: 12 },
  hero: { width: "100%", height: 210, backgroundColor: colores.fondo2 },
  cuerpo: { padding: espacio.l },
  filaEtiquetas: { flexDirection: "row", gap: 6, flexWrap: "wrap", marginBottom: espacio.s },
  titulo: { fontSize: 24, fontWeight: "800", color: colores.tinta },
  precio: { fontSize: 20, fontWeight: "800", color: colores.marca, marginTop: espacio.s },
  descripcion: { fontSize: 15, lineHeight: 22, color: colores.texto, marginTop: espacio.m },
  datos: {
    marginTop: espacio.l,
    backgroundColor: colores.fondo,
    borderRadius: radio.m,
    padding: espacio.m,
    gap: espacio.s,
  },
  dato: { flexDirection: "row", alignItems: "center", gap: 8 },
  datoTexto: { fontSize: 14, color: colores.texto, flex: 1 },
  aval: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: espacio.m,
    backgroundColor: colores.fondo2,
    borderRadius: radio.s,
    padding: espacio.m,
  },
  avalTexto: { color: colores.marcaOscura, fontSize: 13, fontWeight: "700", flex: 1 },
  nota: { fontSize: 12, color: colores.suave, textAlign: "center", marginTop: espacio.m },
});
