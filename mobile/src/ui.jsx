import React from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { colores, espacio, radio, sombra } from "./theme";

export function Btn({ children, onPress, variant = "primary", icon, disabled, style }) {
  const base = [estilos.btn];
  if (variant === "primary") base.push(estilos.btnPrimario);
  if (variant === "secundario") base.push(estilos.btnSecundario);
  if (variant === "peligro") base.push(estilos.btnPeligro);
  if (variant === "fantasma") base.push(estilos.btnFantasma);
  if (disabled) base.push({ opacity: 0.5 });

  const colorTexto =
    variant === "primary" ? "#fff" : variant === "peligro" ? "#fff" : colores.marca;

  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      style={({ pressed }) => [base, sombra, pressed && { opacity: 0.85 }, style]}
      accessibilityRole="button"
    >
      {icon ? <Ionicons name={icon} size={18} color={colorTexto} style={{ marginRight: 6 }} /> : null}
      <Text style={[estilos.btnTexto, { color: colorTexto }]}>{children}</Text>
    </Pressable>
  );
}

export function Campo({ label, style, ...props }) {
  return (
    <View style={{ marginBottom: espacio.m }}>
      {label ? <Text style={estilos.label}>{label}</Text> : null}
      <TextInput
        placeholderTextColor={colores.suave}
        style={[estilos.input, style]}
        {...props}
      />
    </View>
  );
}

export function Chip({ label, activo, onPress, icon }) {
  return (
    <Pressable
      onPress={onPress}
      style={[estilos.chip, activo && estilos.chipOn]}
      accessibilityRole="button"
    >
      {icon ? (
        <Ionicons name={icon} size={14} color={activo ? "#fff" : colores.suave} style={{ marginRight: 4 }} />
      ) : null}
      <Text style={[estilos.chipTexto, activo && { color: "#fff" }]}>{label}</Text>
    </Pressable>
  );
}

/** Fila de chips que se desliza en horizontal (filtros). */
export function FilaChips({ children, style }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={[{ marginBottom: espacio.xs }, style]}
      contentContainerStyle={{ paddingRight: espacio.l, alignItems: "center" }}
      keyboardShouldPersistTaps="handled"
    >
      {children}
    </ScrollView>
  );
}

const TONOS_ETIQUETA = {
  neutro: { fondo: colores.fondo2, color: colores.suave },
  peligro: { fondo: colores.peligroSuave, color: colores.peligro },
  aviso: { fondo: colores.avisoSuave, color: colores.aviso },
  facebook: { fondo: colores.facebook, color: "#ffffff" },
};

export function Etiqueta({ children, tono = "neutro" }) {
  const { fondo, color } = TONOS_ETIQUETA[tono] || TONOS_ETIQUETA.neutro;
  return (
    <View style={[estilos.etiqueta, { backgroundColor: fondo }]}>
      <Text style={{ color, fontSize: 11, fontWeight: "700" }}>{children}</Text>
    </View>
  );
}

export function Vacio({ titulo, texto, accion }) {
  return (
    <View style={estilos.vacio}>
      <Ionicons name="search-outline" size={40} color={colores.lineaFuerte} />
      <Text style={estilos.vacioTitulo}>{titulo}</Text>
      {texto ? <Text style={estilos.vacioTexto}>{texto}</Text> : null}
      {accion}
    </View>
  );
}

export function Cargando({ texto = "Cargando…" }) {
  return (
    <View style={estilos.cargando}>
      <ActivityIndicator color={colores.marca} />
      <Text style={{ color: colores.suave, marginTop: espacio.s }}>{texto}</Text>
    </View>
  );
}

export function Encabezado({ titulo, subtitulo, accion }) {
  return (
    <View style={estilos.encabezado}>
      <View style={{ flex: 1 }}>
        <Text style={estilos.encabezadoTitulo}>{titulo}</Text>
        {subtitulo ? <Text style={estilos.encabezadoSub}>{subtitulo}</Text> : null}
      </View>
      {accion}
    </View>
  );
}

export function Hoja({ visible, onClose, titulo, children }) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={estilos.hojaFondo}>
        <Pressable style={{ flex: 1 }} onPress={onClose} />
        <View style={estilos.hoja}>
          <View style={estilos.hojaCab}>
            <Text style={estilos.hojaTitulo} numberOfLines={1}>
              {titulo}
            </Text>
            <Pressable onPress={onClose} hitSlop={12} accessibilityLabel="Cerrar">
              <Ionicons name="close" size={24} color={colores.tinta} />
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={{ paddingBottom: espacio.xl }}>{children}</ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  btn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    height: 46,
    paddingHorizontal: espacio.l,
    borderRadius: radio.m,
  },
  btnPrimario: { backgroundColor: colores.marca },
  btnSecundario: { backgroundColor: colores.superficie, borderWidth: 1, borderColor: colores.lineaFuerte },
  btnPeligro: { backgroundColor: colores.peligro },
  btnFantasma: { backgroundColor: "transparent" },
  btnTexto: { fontWeight: "700", fontSize: 15 },

  label: { fontSize: 13, fontWeight: "700", color: colores.texto, marginBottom: 6 },
  input: {
    minHeight: 46,
    borderWidth: 1,
    borderColor: colores.linea,
    backgroundColor: colores.superficie,
    borderRadius: radio.s,
    paddingHorizontal: espacio.m,
    paddingVertical: espacio.s,
    fontSize: 15,
    color: colores.tinta,
  },

  chip: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: espacio.m,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: colores.superficie,
    borderWidth: 1,
    borderColor: colores.linea,
    marginRight: espacio.s,
    marginBottom: espacio.s,
  },
  chipOn: { backgroundColor: colores.marca, borderColor: colores.marca },
  chipTexto: { fontSize: 13, fontWeight: "600", color: colores.suave },

  etiqueta: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, alignSelf: "flex-start" },

  vacio: { alignItems: "center", padding: espacio.xl },
  vacioTitulo: { fontSize: 17, fontWeight: "700", color: colores.tinta, marginTop: espacio.m },
  vacioTexto: { color: colores.suave, textAlign: "center", marginTop: espacio.s, marginBottom: espacio.l },

  cargando: { alignItems: "center", padding: espacio.xl },

  encabezado: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: espacio.l,
    paddingTop: espacio.s,
    paddingBottom: espacio.m,
  },
  encabezadoTitulo: { fontSize: 24, fontWeight: "800", color: colores.tinta },
  encabezadoSub: { fontSize: 13, color: colores.suave, marginTop: 2 },

  hojaFondo: { flex: 1, backgroundColor: "rgba(20,27,43,0.45)" },
  hoja: {
    maxHeight: "88%",
    backgroundColor: colores.superficie,
    borderTopLeftRadius: radio.l,
    borderTopRightRadius: radio.l,
    paddingHorizontal: espacio.l,
    paddingTop: espacio.m,
  },
  hojaCab: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: espacio.m,
  },
  hojaTitulo: { fontSize: 18, fontWeight: "800", color: colores.tinta, flex: 1, marginRight: espacio.m },
});
