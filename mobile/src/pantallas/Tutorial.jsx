import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as Speech from "expo-speech";
import Ionicons from "@expo/vector-icons/Ionicons";
import { colores, espacio, radio } from "../theme";
import { Btn, Encabezado } from "../ui";
import Pantalla from "../Pantalla";

const PASOS = [
  ["bar-chart-outline", "Economía Local", "Mira servicios y productos de tu sector, ordenados por cercanía."],
  ["hand-left-outline", "Economía Solidaria", "Pide u ofrece favores: préstamos, donaciones, habilidades o movilidad."],
  ["warning-outline", "Emergencia", "Reporta necesidades y llama a los números de ayuda con un toque."],
  ["add-circle-outline", "Publicar", "Desde el botón Publicar creas un servicio, producto, favor o emergencia."],
  ["chatbubble-ellipses-outline", "Contactar", "Abre WhatsApp con el vecino; el chat interno llega en la fase 2."],
  ["thumbs-up-outline", "Vistos buenos", "Recomienda a quien te atendió bien (máximo 5 al día)."],
];

export default function Tutorial() {
  const [leyendo, setLeyendo] = useState(false);

  const leer = () => {
    const texto = PASOS.map(([, t, d]) => `${t}. ${d}`).join(" ");
    if (leyendo) {
      Speech.stop();
      setLeyendo(false);
      return;
    }
    Speech.speak(texto, {
      language: "es-PE",
      onDone: () => setLeyendo(false),
      onStopped: () => setLeyendo(false),
    });
    setLeyendo(true);
  };

  return (
    <Pantalla>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: espacio.l, paddingBottom: espacio.xl * 2 }}>
      <Encabezado titulo="Cómo funciona" subtitulo="Seis pasos para moverte en el barrio" />

      <Btn variant="secundario" icon={leyendo ? "stop-outline" : "volume-high-outline"} onPress={leer}>
        {leyendo ? "Detener lectura" : "Leer en voz alta"}
      </Btn>

      <View style={{ marginTop: espacio.l, gap: espacio.s }}>
        {PASOS.map(([icono, titulo, detalle], i) => (
          <View key={titulo} style={estilos.paso}>
            <View style={estilos.numero}>
              <Text style={estilos.numeroTexto}>{i + 1}</Text>
            </View>
            <Ionicons name={icono} size={22} color={colores.marca} />
            <View style={{ flex: 1 }}>
              <Text style={estilos.titulo}>{titulo}</Text>
              <Text style={estilos.detalle}>{detalle}</Text>
            </View>
          </View>
        ))}
      </View>

      <View style={estilos.nota}>
        <Ionicons name="information-circle-outline" size={18} color={colores.info} />
        <Text style={estilos.notaTexto}>
          Tu ubicación se muestra aproximada (300-500 m) y tu teléfono solo lo ven vecinos con
          sesión iniciada.
        </Text>
      </View>
      </ScrollView>
    </Pantalla>
  );
}

const estilos = StyleSheet.create({
  paso: {
    flexDirection: "row",
    alignItems: "center",
    gap: espacio.m,
    backgroundColor: colores.superficie,
    borderRadius: radio.m,
    borderWidth: 1,
    borderColor: colores.linea,
    padding: espacio.m,
  },
  numero: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colores.fondo2,
    alignItems: "center",
    justifyContent: "center",
  },
  numeroTexto: { fontSize: 12, fontWeight: "800", color: colores.marca },
  titulo: { fontSize: 14, fontWeight: "700", color: colores.tinta },
  detalle: { fontSize: 12, color: colores.suave, marginTop: 2, lineHeight: 17 },
  nota: {
    flexDirection: "row",
    gap: 8,
    backgroundColor: colores.infoSuave,
    borderRadius: radio.s,
    padding: espacio.m,
    marginTop: espacio.l,
  },
  notaTexto: { flex: 1, fontSize: 12, color: colores.info, lineHeight: 17 },
});
