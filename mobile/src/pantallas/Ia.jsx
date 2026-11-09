import React, { useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../api";
import { colores, espacio, radio } from "../theme";
import { Btn, Campo, Encabezado, Etiqueta, Cargando } from "../ui";
import Pantalla from "../Pantalla";

export default function Ia({ navigation }) {
  const qc = useQueryClient();
  const { data: config, isLoading } = useQuery({
    queryKey: ["ia-config"],
    queryFn: () => api.get("/api/ia/config"),
  });

  const [apiKey, setApiKey] = useState("");
  const [modelo, setModelo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [trabajando, setTrabajando] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const estado = config?.estado || { total: 0, pendientes: 0, aprobados: 0, rechazados: 0 };
  const auto = config?.auto;

  const fecha = (iso) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("es-PE", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  const guardar = async () => {
    setGuardando(true);
    setMensaje("");
    try {
      await api.put("/api/ia/config", {
        api_key: apiKey.trim() || undefined,
        modelo: modelo.trim() || undefined,
      });
      setApiKey("");
      await qc.invalidateQueries({ queryKey: ["ia-config"] });
      setMensaje("Configuración guardada.");
    } catch (e) {
      setMensaje(e.message);
    } finally {
      setGuardando(false);
    }
  };

  const revisar = async (todos) => {
    setTrabajando(true);
    setMensaje("Revisando con IA…");
    let revisados = 0;
    try {
      let restantes = todos ? estado.pendientes : 1;
      while (restantes > 0) {
        const r = await api.post("/api/ia/revisar", { limite: 5 });
        revisados += r.revisados;
        qc.setQueryData(["ia-config"], (prev) => prev && { ...prev, estado: r.estado });
        setMensaje(
          `Revisados ${revisados}: ${r.estado.aprobados} aprobados y ${r.estado.rechazados} rechazados. ` +
            `Quedan ${r.estado.pendientes} pendientes.`
        );
        if (!todos || r.revisados === 0) break; // evita bucles si algo falla
        restantes = r.estado.pendientes;
      }
      qc.invalidateQueries({ queryKey: ["lista"] });
      qc.invalidateQueries({ queryKey: ["ia-config"] });
    } catch (e) {
      setMensaje(e.message);
    } finally {
      setTrabajando(false);
    }
  };

  const revisarTodo = () => {
    if (!estado.pendientes) {
      Alert.alert("Nada pendiente", "Todas las publicaciones ya fueron revisadas.");
      return;
    }
    Alert.alert(
      "Revisar todas",
      `Se revisarán ${estado.pendientes} publicaciones. Puede tardar varios minutos y consume créditos de OpenRouter.`,
      [
        { text: "Cancelar", style: "cancel" },
        { text: "Revisar", onPress: () => revisar(true) },
      ]
    );
  };

  const escanear = async () => {
    setTrabajando(true);
    setMensaje("Scrapeando Facebook… puede tardar varios minutos.");
    try {
      const r = await api.post("/api/ia/scrape", {});
      setMensaje(`Scrapeo listo: ${r.saved} nuevas, ${r.total_in_db} en total.`);
      qc.invalidateQueries({ queryKey: ["ia-config"] });
      qc.invalidateQueries({ queryKey: ["lista"] });
    } catch (e) {
      setMensaje(e.message);
    } finally {
      setTrabajando(false);
    }
  };

  if (isLoading) return <Cargando />;

  return (
    <Pantalla>
      <ScrollView contentContainerStyle={estilos.cuerpo} keyboardShouldPersistTaps="handled">
        <Encabezado
          titulo="Revisión con IA"
          subtitulo="Limpia las publicaciones traídas de Facebook"
          accion={
            <Btn variant="fantasma" onPress={() => navigation.goBack()}>
              Cerrar
            </Btn>
          }
        />

        <View style={estilos.tarjeta}>
          <Text style={estilos.tarjetaTitulo}>Estado</Text>
          <View style={estilos.metricas}>
            <Metrica valor={estado.total} etiqueta="Total" />
            <Metrica valor={estado.pendientes} etiqueta="Pendientes" />
            <Metrica valor={estado.aprobados} etiqueta="Aprobadas" />
            <Metrica valor={estado.rechazados} etiqueta="Rechazadas" />
          </View>
          <View style={{ flexDirection: "row", marginTop: espacio.s }}>
            <Etiqueta tono={config?.configurada ? "neutro" : "peligro"}>
              {config?.configurada ? "API key configurada" : "Falta la API key"}
            </Etiqueta>
          </View>
        </View>

        <Text style={estilos.seccion}>OpenRouter</Text>
        <Campo
          label="API key (sk-or-v1-...)"
          value={apiKey}
          onChangeText={setApiKey}
          secureTextEntry
          autoCapitalize="none"
          placeholder={config?.configurada ? "•••••••• (guardada)" : "Pega tu API key"}
        />
        <Campo
          label="Modelo de visión"
          value={modelo}
          onChangeText={setModelo}
          autoCapitalize="none"
          placeholder={config?.modelo || "google/gemini-2.5-flash"}
        />

        <Btn variant="secundario" onPress={guardar} disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar configuración"}
        </Btn>

        <Text style={estilos.seccion}>Automatización</Text>
        <View style={estilos.tarjeta}>
          <Text style={estilos.ayuda}>
            Scrapeo programado cada {auto?.scrape_cada_horas ?? 6} h:{" "}
            {auto?.puede_scrapear
              ? "sesión de Facebook lista."
              : "falta sesión de Facebook (FB_EMAIL / FB_PASSWORD o data/fb_state.json)."}
          </Text>
          <Text style={estilos.ayuda}>
            Último: {fecha(auto?.ultimo_scrape)} · Próximo: {fecha(auto?.proximo_scrape)}
          </Text>
          {auto?.ultimo_error ? (
            <Text style={estilos.error}>Último error: {auto.ultimo_error}</Text>
          ) : null}
          <Btn variant="secundario" onPress={escanear} disabled={trabajando} style={{ marginTop: espacio.s }}>
            Escanear Facebook ahora
          </Btn>
          <Text style={estilos.nota}>
            Si el escaneo tarda más de ~100 s, el túnel cortará la respuesta; en ese caso el
            planificador lo hará solo en segundo plano.
          </Text>
        </View>

        <Text style={estilos.seccion}>Revisar publicaciones</Text>
        <Text style={estilos.ayuda}>
          La IA lee el texto y la foto de cada publicación, la traduce, decide si es una oferta
          real de servicio y extrae teléfono y ubicación (aunque solo aparezcan en la imagen).
          Las que no cumplen se ocultan de Economía Local.
        </Text>

        <View style={{ gap: espacio.s, marginTop: espacio.m }}>
          <Btn onPress={() => revisar(false)} disabled={trabajando || !config?.configurada}>
            {trabajando ? "Revisando…" : "Revisar 5 pendientes"}
          </Btn>
          <Btn
            variant="secundario"
            onPress={revisarTodo}
            disabled={trabajando || !config?.configurada || !estado.pendientes}
          >
            Revisar todas ({estado.pendientes})
          </Btn>
        </View>

        {mensaje ? (
          <View style={estilos.mensaje}>
            <Ionicons name="sparkles-outline" size={16} color={colores.marca} />
            <Text style={estilos.mensajeTexto}>{mensaje}</Text>
          </View>
        ) : null}

        <Text style={estilos.nota}>
          La API key se guarda en el servidor (tabla de ajustes), no en el teléfono. Nunca se
          devuelve al cliente.
        </Text>
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
  cuerpo: { padding: espacio.l, paddingBottom: espacio.xl * 2 },
  tarjeta: {
    backgroundColor: colores.superficie,
    borderRadius: radio.m,
    borderWidth: 1,
    borderColor: colores.linea,
    padding: espacio.m,
  },
  tarjetaTitulo: { fontSize: 14, fontWeight: "800", color: colores.tinta, marginBottom: espacio.s },
  metricas: { flexDirection: "row", gap: espacio.s },
  metrica: {
    flex: 1,
    backgroundColor: colores.fondo,
    borderRadius: radio.s,
    paddingVertical: espacio.s,
    alignItems: "center",
  },
  metricaValor: { fontSize: 18, fontWeight: "800", color: colores.marca },
  metricaEtiqueta: { fontSize: 10, color: colores.suave, marginTop: 2, textAlign: "center" },
  seccion: { fontSize: 16, fontWeight: "800", color: colores.tinta, marginTop: espacio.l, marginBottom: espacio.s },
  ayuda: { fontSize: 12, color: colores.suave, lineHeight: 18 },
  mensaje: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    backgroundColor: colores.fondo,
    borderRadius: radio.s,
    padding: espacio.m,
    marginTop: espacio.m,
  },
  mensajeTexto: { flex: 1, fontSize: 12, color: colores.texto },
  nota: { fontSize: 11, color: colores.suave, marginTop: espacio.l, textAlign: "center" },
  error: { fontSize: 11, color: colores.peligro, marginTop: espacio.s },
});
