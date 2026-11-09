import React, { useMemo, useState } from "react";
import {
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import Ionicons from "@expo/vector-icons/Ionicons";
import { api, fotoUrl } from "./api";
import { useAuth } from "./Auth";
import { useZona } from "./Zona";
import { colores, espacio, radio } from "./theme";
import { Btn, Campo, Chip, FilaChips } from "./ui";
import Pantalla from "./Pantalla";

const CATS = [
  "gasfitería",
  "carpintería",
  "electricidad",
  "cerrajería",
  "clases",
  "alimentos",
  "paseo de mascotas",
  "herramientas",
  "movilidad",
  "préstamo",
  "otros",
];

const SUBTIPOS = [
  { value: "prestamo", label: "Préstamo de cosas" },
  { value: "ayuda_temporal", label: "Ayuda temporal" },
  { value: "donacion", label: "Donación de materiales" },
  { value: "intercambio_habilidades", label: "Intercambio de habilidades" },
  { value: "movilidad", label: "Movilidad solidaria" },
];

const NECESIDADES = [
  ["agua_potable", "Agua"],
  ["alimentos", "Alimentos"],
  ["balde_bidon", "Bidones"],
  ["techo", "Techo"],
  ["abrigo", "Abrigo"],
  ["higiene", "Higiene"],
  ["salud", "Salud"],
  ["herramientas", "Herramientas"],
  ["movilidad", "Movilidad"],
  ["alojamiento", "Alojamiento"],
  ["energia", "Energía"],
  ["otro", "Otro"],
];

const PAGOS = ["yape", "plin", "efectivo", "transferencia"];

const POLITICAS = [
  { value: "contra_entrega", label: "Contra entrega" },
  { value: "mitad_mitad", label: "Mitad y mitad" },
  { value: "al_terminar", label: "Al terminar" },
];

const MODOS = [
  { value: "servicio", label: "Servicio" },
  { value: "producto", label: "Producto" },
  { value: "favor", label: "Favor" },
  { value: "emergencia", label: "Emergencia" },
];

export default function Publicar({ navigation, route }) {
  const inicial = route?.params?.modo || "servicio";
  const editando = route?.params?.publicacion || null;
  const esEdicion = Boolean(editando);

  const modoInicial = (() => {
    if (!editando) return inicial;
    if (editando.es_emergencia) return "emergencia";
    if (String(editando.tipo || "").startsWith("favor")) return "favor";
    return editando.tipo === "producto" ? "producto" : "servicio";
  })();
  const precioInicial = editando?.precio || "";
  const numeroPrecio = /^S\/\s*([\d.,]+)/.exec(precioInicial);

  const { usuario } = useAuth();
  const { zona, zonas, usarGPS } = useZona();
  const qc = useQueryClient();

  const [modo, setModo] = useState(modoInicial);
  const [lado, setLado] = useState(
    editando && String(editando.tipo || "").endsWith("ofrecido") ? "ofrezco" : "necesito"
  );
  const [titulo, setTitulo] = useState(editando?.titulo || "");
  const [descripcion, setDescripcion] = useState(editando?.descripcion || "");
  const [categoria, setCategoria] = useState(editando?.categoria || "gasfitería");
  const [precio, setPrecio] = useState(numeroPrecio ? numeroPrecio[1].replace(",", ".") : "");
  const [aConvenir, setAConvenir] = useState(precioInicial === "A convenir");
  const [stock, setStock] = useState(editando?.stock != null ? String(editando.stock) : "");
  const [pagos, setPagos] = useState(() => {
    const medios = String(editando?.medios_pago || "").split(",").filter(Boolean);
    return medios.length && !medios.includes("intercambio") ? medios : ["yape", "efectivo"];
  });
  const [politica, setPolitica] = useState(editando?.politica_pago || "contra_entrega");
  const [subtipo, setSubtipo] = useState(editando?.subtipo_favor || "prestamo");
  const [franja, setFranja] = useState(editando?.franja_horaria || "");
  const [punto, setPunto] = useState(editando?.punto_encuentro || "");
  const [checklist, setChecklist] = useState(Boolean(editando?.checklist_ok));
  const [necesidad, setNecesidad] = useState(editando?.necesidad || "agua_potable");
  const [fotos, setFotos] = useState(() => (editando?.fotos || []).slice(0, 3));
  const [wa, setWa] = useState(editando ? Boolean(editando.whatsapp) : true);
  const [tel, setTel] = useState(editando?.whatsapp || usuario?.telefono || "");
  const [mostrar, setMostrar] = useState(
    editando ? Boolean(editando.mostrar_contacto) : true
  );
  const [gps, setGps] = useState(null);
  const [subiendo, setSubiendo] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const esEmergencia = modo === "emergencia";
  const esFavor = modo === "favor" || esEmergencia;
  const tipo = esEmergencia
    ? lado === "ofrezco"
      ? "favor_ofrecido"
      : "favor_solicitado"
    : esFavor
      ? lado === "ofrezco"
        ? "favor_ofrecido"
        : "favor_solicitado"
      : modo;
  const esProducto = tipo === "producto";
  const esMovilidad = esFavor && !esEmergencia && subtipo === "movilidad";
  const zonaActual = zona;
  const zonaConocida = zonas.some((z) => z.nombre === zonaActual);

  const usarUbicacion = async () => {
    try {
      const c = await usarGPS();
      setGps(c);
    } catch (e) {
      Alert.alert("Sin ubicación", e.message);
    }
  };

  const agregarFoto = async () => {
    if (fotos.length >= 3) return;
    const permiso = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permiso.granted) {
      Alert.alert("Permiso necesario", "Necesitamos acceso a tus fotos.");
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.45,
      base64: true,
    });
    if (res.canceled || !res.assets?.length) return;
    const asset = res.assets[0];
    const mime = asset.mimeType || "image/jpeg";
    setSubiendo(true);
    try {
      const data = `data:${mime};base64,${asset.base64}`;
      const r = await api.post("/api/fotos", { data });
      setFotos((prev) => [...prev, r.url]);
    } catch (e) {
      Alert.alert("No se pudo subir la foto", e.message);
    } finally {
      setSubiendo(false);
    }
  };

  const validar = () => {
    if (titulo.trim().length < 3) return "Escribe un título de al menos 3 caracteres.";
    if (descripcion.trim().length < 10) return "Cuenta un poco más en la descripción (10 caracteres).";
    if (!esFavor && !aConvenir && !Number(precio)) return "Escribe un precio en soles o marca «A convenir».";
    if (esMovilidad && !franja.trim()) return "Indica la franja horaria.";
    if (esMovilidad && !punto.trim()) return "Indica un punto de encuentro público.";
    if (esMovilidad && !checklist) return "Confirma la lista de seguridad.";
    if (wa && !/^9\d{8}$/.test(String(tel))) return "Escribe un celular de 9 dígitos o desactiva WhatsApp.";
    if (!zonaConocida && !gps) return "Comparte tu ubicación para ubicar tu sector.";
    return "";
  };

  const publicar = async () => {
    const err = validar();
    if (err) {
      setError(err);
      return;
    }
    setError("");
    setGuardando(true);
    try {
      const precioFinal = esFavor
        ? "Gratis / intercambio"
        : aConvenir
          ? "A convenir"
          : `S/ ${Number(precio).toFixed(2)}`;

      if (esEdicion) {
        await api.patch(`/api/publicaciones/${editando.id}`, {
          categoria: esEmergencia ? "otros" : categoria,
          subtipo_favor: esEmergencia
            ? lado === "ofrezco"
              ? "donacion"
              : "ayuda_temporal"
            : esFavor
              ? subtipo
              : null,
          titulo: titulo.trim(),
          descripcion: descripcion.trim(),
          precio: precioFinal,
          stock: esProducto ? (stock === "" ? null : Number(stock)) : null,
          medios_pago: esFavor ? "intercambio" : pagos.join(",") || "efectivo",
          politica_pago: politica,
          zona: zonaActual,
          punto_encuentro: punto,
          franja_horaria: franja,
          checklist_ok: checklist,
          necesidad: esEmergencia ? necesidad : null,
          mostrar_contacto: mostrar,
          whatsapp: wa,
          telefono_whatsapp: wa ? tel : "",
          fotos,
        });
      } else {
        await api.post("/api/publicaciones", {
          tipo,
          categoria: esEmergencia ? "otros" : categoria,
          subtipo_favor: esEmergencia
            ? lado === "ofrezco"
              ? "donacion"
              : "ayuda_temporal"
            : esFavor
              ? subtipo
              : null,
          titulo: titulo.trim(),
          descripcion: descripcion.trim(),
          precio: precioFinal,
          stock: esProducto ? (stock === "" ? null : Number(stock)) : null,
          medios_pago: esFavor ? "intercambio" : pagos.join(",") || "efectivo",
          politica_pago: politica,
          zona: zonaActual,
          lat: gps?.lat ?? null,
          lng: gps?.lng ?? null,
          punto_encuentro: punto,
          franja_horaria: franja,
          checklist_ok: checklist,
          es_emergencia: esEmergencia,
          necesidad: esEmergencia ? necesidad : null,
          mostrar_contacto: mostrar,
          whatsapp: wa,
          telefono_whatsapp: wa ? tel : "",
          fotos,
          client_id: `c-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        });
      }

      qc.invalidateQueries({ queryKey: ["lista"] });
      qc.invalidateQueries({ queryKey: ["mis-publicaciones"] });
      qc.invalidateQueries({ queryKey: ["recursos"] });
      qc.invalidateQueries({ queryKey: ["publicacion", editando?.id] });
      Alert.alert(esEdicion ? "Guardado" : "¡Publicado!", esEdicion ? "Tu publicación quedó actualizada." : "Ya lo ven tus vecinos.");
      navigation.goBack();
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Pantalla style={{ backgroundColor: colores.superficie }}>
    <ScrollView style={{ flex: 1, backgroundColor: colores.superficie }} contentContainerStyle={{ padding: espacio.l }}>
      <View style={estilos.cabecera}>
        <Text style={estilos.titulo}>{esEdicion ? "Editar publicación" : "¿Qué quieres publicar?"}</Text>
        <Pressable onPress={() => navigation.goBack()} hitSlop={12} accessibilityLabel="Cerrar">
          <Ionicons name="close" size={26} color={colores.tinta} />
        </Pressable>
      </View>

      {!esEdicion ? (
        <>
          <FilaChips>
            {MODOS.map((m) => (
              <Chip key={m.value} label={m.label} activo={modo === m.value} onPress={() => setModo(m.value)} />
            ))}
          </FilaChips>

          {esFavor ? (
            <FilaChips>
              <Chip label="Necesito" activo={lado === "necesito"} onPress={() => setLado("necesito")} />
              <Chip label="Ofrezco" activo={lado === "ofrezco"} onPress={() => setLado("ofrezco")} />
            </FilaChips>
          ) : (
            <FilaChips>
              <Chip label="Servicio" activo={modo === "servicio"} onPress={() => setModo("servicio")} />
              <Chip label="Producto" activo={modo === "producto"} onPress={() => setModo("producto")} />
            </FilaChips>
          )}
        </>
      ) : null}

      <Campo
        label="Título"
        value={titulo}
        onChangeText={setTitulo}
        placeholder={esEmergencia ? "¿Qué se necesita?" : "Ej.: Gasfitero para fugas"}
        maxLength={120}
      />

      <Campo
        label="Descripción"
        value={descripcion}
        onChangeText={setDescripcion}
        placeholder="Cuenta los detalles"
        multiline
        numberOfLines={4}
        style={{ minHeight: 96, textAlignVertical: "top" }}
        maxLength={2000}
      />

      {!esEmergencia ? (
        <>
          <Text style={estilos.label}>Categoría</Text>
          <FilaChips>
            {CATS.map((c) => (
              <Chip key={c} label={c} activo={categoria === c} onPress={() => setCategoria(c)} />
            ))}
          </FilaChips>
        </>
      ) : null}

      {esEmergencia ? (
        <>
          <Text style={estilos.label}>¿De qué se trata?</Text>
          <FilaChips>
            {NECESIDADES.map(([v, l]) => (
              <Chip key={v} label={l} activo={necesidad === v} onPress={() => setNecesidad(v)} />
            ))}
          </FilaChips>
        </>
      ) : null}

      {esFavor && !esEmergencia ? (
        <>
          <Text style={estilos.label}>Tipo de favor</Text>
          <FilaChips>
            {SUBTIPOS.map((s) => (
              <Chip key={s.value} label={s.label} activo={subtipo === s.value} onPress={() => setSubtipo(s.value)} />
            ))}
          </FilaChips>
        </>
      ) : null}

      {esMovilidad ? (
        <>
          <Campo label="Franja horaria" value={franja} onChangeText={setFranja} placeholder="7:00 a 8:00" />
          <Campo label="Punto de encuentro público" value={punto} onChangeText={setPunto} placeholder="Parque Central" />
          <FilaSwitch
            titulo="Confirmo que no publico el colegio, la dirección ni datos del menor"
            valor={checklist}
            onChange={setChecklist}
          />
        </>
      ) : null}

      {!esFavor ? (
        <>
          <Campo
            label="Precio (S/)"
            value={precio}
            onChangeText={setPrecio}
            keyboardType="decimal-pad"
            placeholder="40"
            editable={!aConvenir}
          />
          <FilaSwitch titulo="A convenir" valor={aConvenir} onChange={setAConvenir} />
          {esProducto ? (
            <Campo label="Stock disponible" value={stock} onChangeText={setStock} keyboardType="number-pad" placeholder="3" />
          ) : null}

          <Text style={estilos.label}>Formas de pago</Text>
          <FilaChips>
            {PAGOS.map((p) => (
              <Chip
                key={p}
                label={p}
                activo={pagos.includes(p)}
                onPress={() =>
                  setPagos((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]))
                }
              />
            ))}
          </FilaChips>

          <Text style={estilos.label}>Acuerdo de pago</Text>
          <FilaChips>
            {POLITICAS.map((p) => (
              <Chip key={p.value} label={p.label} activo={politica === p.value} onPress={() => setPolitica(p.value)} />
            ))}
          </FilaChips>
        </>
      ) : null}

      <Text style={estilos.label}>Fotos ({fotos.length}/3)</Text>
      <View style={estilos.fila}>
        {fotos.map((f) => (
          <View key={f} style={{ marginRight: espacio.s }}>
            <Image source={{ uri: fotoUrl(f) }} style={estilos.mini} />
            <Pressable
              onPress={() => setFotos((prev) => prev.filter((x) => x !== f))}
              style={estilos.quitarFoto}
              hitSlop={10}
              accessibilityLabel="Quitar foto"
            >
              <Ionicons name="close" size={13} color="#fff" />
            </Pressable>
          </View>
        ))}
        {fotos.length < 3 ? (
          <Pressable onPress={agregarFoto} style={estilos.agregarFoto} disabled={subiendo}>
            <Ionicons name={subiendo ? "hourglass-outline" : "camera-outline"} size={22} color={colores.suave} />
            <Text style={{ fontSize: 11, color: colores.suave, marginTop: 2 }}>
              {subiendo ? "Subiendo…" : "Agregar"}
            </Text>
          </Pressable>
        ) : null}
      </View>

      <View style={estilos.zonaCaja}>
        <View style={{ flex: 1 }}>
          <Text style={estilos.label}>Sector</Text>
          <Text style={{ color: colores.tinta, fontWeight: "600" }}>{zonaActual}</Text>
        </View>
        <Btn variant="secundario" icon="navigate-outline" onPress={usarUbicacion}>
          {gps ? "Ubicación lista" : "Usar mi GPS"}
        </Btn>
      </View>

      <FilaSwitch titulo="Acepto WhatsApp" valor={wa} onChange={setWa} />
      {wa ? (
        <Campo label="Celular para WhatsApp" value={tel} onChangeText={setTel} keyboardType="phone-pad" maxLength={9} placeholder="987654321" />
      ) : null}
      <FilaSwitch titulo="Mostrar mi contacto" valor={mostrar} onChange={setMostrar} />

      {error ? <Text style={estilos.error}>{error}</Text> : null}

      <Btn onPress={publicar} disabled={guardando} style={{ marginTop: espacio.s }}>
        {guardando ? "Publicando…" : "Publicar"}
      </Btn>
      <Text style={estilos.nota}>
        Al publicar aceptas el aviso de privacidad. Tu ubicación se muestra aproximada (300-500 m).
      </Text>
    </ScrollView>
    </Pantalla>
  );
}

function FilaSwitch({ titulo, valor, onChange }) {
  return (
    <View style={estilos.switchFila}>
      <Text style={estilos.switchTexto}>{titulo}</Text>
      <Switch value={valor} onValueChange={onChange} trackColor={{ true: colores.marca }} />
    </View>
  );
}

const estilos = StyleSheet.create({
  cabecera: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: espacio.m },
  titulo: { fontSize: 22, fontWeight: "800", color: colores.tinta, flex: 1 },
  fila: { flexDirection: "row", flexWrap: "wrap", marginBottom: espacio.s },
  label: { fontSize: 13, fontWeight: "700", color: colores.texto, marginTop: espacio.m, marginBottom: 6 },
  switchFila: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: espacio.s,
    gap: espacio.m,
  },
  switchTexto: { flex: 1, fontSize: 14, color: colores.texto },
  mini: { width: 72, height: 72, borderRadius: radio.s },
  quitarFoto: {
    position: "absolute",
    top: -6,
    right: -6,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colores.peligro,
    alignItems: "center",
    justifyContent: "center",
  },
  agregarFoto: {
    width: 72,
    height: 72,
    borderRadius: radio.s,
    borderWidth: 1,
    borderColor: colores.lineaFuerte,
    borderStyle: "dashed",
    alignItems: "center",
    justifyContent: "center",
  },
  zonaCaja: {
    flexDirection: "row",
    alignItems: "center",
    gap: espacio.m,
    backgroundColor: colores.fondo,
    borderRadius: radio.m,
    padding: espacio.m,
    marginTop: espacio.m,
  },
  error: { color: colores.peligro, marginTop: espacio.m, fontWeight: "600" },
  nota: { fontSize: 11, color: colores.suave, textAlign: "center", marginTop: espacio.m },
});
