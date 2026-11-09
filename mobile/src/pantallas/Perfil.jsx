import React, { useState } from "react";
import { Alert, Image, ScrollView, StyleSheet, Text, View } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { api } from "../api";
import { useAuth } from "../Auth";
import { useZona } from "../Zona";
import { colores, espacio, radio } from "../theme";
import { Btn, Campo, Chip, Encabezado, Etiqueta, FilaChips, Hoja } from "../ui";
import Pantalla from "../Pantalla";

export default function Perfil({ navigation }) {
  const { usuario, salir, recargar } = useAuth();
  const { zonas } = useZona();

  const [editando, setEditando] = useState(false);
  const [eNombre, setENombre] = useState("");
  const [eTelefono, setETelefono] = useState("");
  const [eZona, setEZona] = useState("Piura Centro");
  const [eYape, setEYape] = useState("");
  const [ePlin, setEPlin] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  const abrirEdicion = () => {
    setENombre(usuario.nombre || "");
    setETelefono(usuario.telefono || "");
    setEZona(usuario.zona || "Piura Centro");
    setEYape(usuario.yape || "");
    setEPlin(usuario.plin || "");
    setError("");
    setEditando(true);
  };

  const guardar = async () => {
    setError("");
    setGuardando(true);
    try {
      await api.put("/api/perfil", {
        nombre: eNombre.trim(),
        telefono: eTelefono,
        zona: eZona,
        yape: eYape,
        plin: ePlin,
      });
      await recargar();
      setEditando(false);
      Alert.alert("Guardado", "Tus datos quedaron actualizados.");
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  };

  // --- Sin sesión: elegir entre entrar o crear cuenta --------------------
  if (!usuario) {
    return (
      <Pantalla>
        <ScrollView contentContainerStyle={estilos.cuerpo}>
          <Encabezado titulo="Mi cuenta" subtitulo="Entra para publicar y contactar vecinos" />

          <View style={estilos.hero}>
            <Image
              source={require("../../assets/logo.png")}
              style={estilos.logo}
              resizeMode="contain"
            />
            <Text style={estilos.heroTexto}>
              Publica servicios, pide favores y coordina con tu barrio. Sin cuenta puedes mirar,
              pero para contactar necesitas entrar.
            </Text>
          </View>

          <View style={{ gap: espacio.s, marginTop: espacio.l }}>
            <Btn icon="log-in-outline" onPress={() => navigation.navigate("Entrar")}>
              Iniciar sesión
            </Btn>
            <Btn
              variant="secundario"
              icon="person-add-outline"
              onPress={() => navigation.navigate("Registro")}
            >
              Crear cuenta
            </Btn>
            <Btn variant="fantasma" icon="book-outline" onPress={() => navigation.navigate("Tutorial")}>
              Ver el tutorial
            </Btn>
          </View>
        </ScrollView>
      </Pantalla>
    );
  }

  // --- Con sesión: perfil + modal de edición -----------------------------
  return (
    <Pantalla>
      <ScrollView contentContainerStyle={estilos.cuerpo}>
        <Encabezado
          titulo={usuario.nombre}
          subtitulo={`${usuario.telefono} · ${usuario.zona}`}
          accion={<Etiqueta tono={usuario.rol === "vecino" ? "neutro" : "aviso"}>{usuario.rol}</Etiqueta>}
        />

        <View style={estilos.tarjeta}>
          <Dato icono="call-outline" etiqueta="Celular" valor={usuario.telefono || "—"} />
          <Dato icono="location-outline" etiqueta="Sector" valor={usuario.zona} />
          <Dato icono="wallet-outline" etiqueta="Yape" valor={usuario.yape || "—"} />
          <Dato icono="card-outline" etiqueta="Plin" valor={usuario.plin || "—"} />
          <Dato
            icono="shield-checkmark-outline"
            etiqueta="Teléfono verificado"
            valor={usuario.telefono_verificado ? "Sí" : "No"}
          />
        </View>

        <View style={{ gap: espacio.s, marginTop: espacio.l }}>
          <Btn variant="secundario" icon="create-outline" onPress={abrirEdicion}>
            Editar mis datos
          </Btn>
          <Btn variant="secundario" icon="book-outline" onPress={() => navigation.navigate("Tutorial")}>
            Ver el tutorial
          </Btn>
          <Btn variant="secundario" icon="sparkles-outline" onPress={() => navigation.navigate("Ia")}>
            Revisión con IA
          </Btn>
          <Btn
            variant="peligro"
            icon="log-out-outline"
            onPress={() =>
              Alert.alert("Cerrar sesión", "¿Salir de tu cuenta?", [
                { text: "Cancelar", style: "cancel" },
                { text: "Salir", style: "destructive", onPress: salir },
              ])
            }
          >
            Cerrar sesión
          </Btn>
        </View>
      </ScrollView>

      <Hoja visible={editando} onClose={() => setEditando(false)} titulo="Editar mis datos">
        <Campo label="Nombre" value={eNombre} onChangeText={setENombre} />
        <Campo
          label="Teléfono"
          value={eTelefono}
          onChangeText={(v) => setETelefono(v.replace(/\D/g, ""))}
          keyboardType="phone-pad"
          maxLength={9}
        />

        <Text style={estilos.label}>Sector</Text>
        <FilaChips>
          {zonas.map((z) => (
            <Chip key={z.nombre} label={z.nombre} activo={eZona === z.nombre} onPress={() => setEZona(z.nombre)} />
          ))}
        </FilaChips>

        <Campo
          label="Yape"
          value={eYape}
          onChangeText={(v) => setEYape(v.replace(/\D/g, ""))}
          keyboardType="phone-pad"
          maxLength={9}
        />
        <Campo
          label="Plin"
          value={ePlin}
          onChangeText={(v) => setEPlin(v.replace(/\D/g, ""))}
          keyboardType="phone-pad"
          maxLength={9}
        />

        {error ? <Text style={estilos.error}>{error}</Text> : null}

        <View style={{ flexDirection: "row", gap: espacio.s }}>
          <Btn onPress={guardar} disabled={guardando} style={{ flex: 1 }}>
            {guardando ? "Guardando…" : "Guardar"}
          </Btn>
          <Btn variant="secundario" onPress={() => setEditando(false)} style={{ flex: 1 }}>
            Cancelar
          </Btn>
        </View>
      </Hoja>
    </Pantalla>
  );
}

function Dato({ icono, etiqueta, valor }) {
  return (
    <View style={estilos.dato}>
      <Ionicons name={icono} size={18} color={colores.suave} />
      <Text style={estilos.datoEtiqueta}>{etiqueta}</Text>
      <Text style={estilos.datoValor} numberOfLines={1}>
        {valor}
      </Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  cuerpo: { padding: espacio.l, paddingBottom: espacio.xl * 2 },
  hero: {
    backgroundColor: colores.superficie,
    borderRadius: radio.m,
    borderWidth: 1,
    borderColor: colores.linea,
    padding: espacio.l,
    alignItems: "center",
    marginTop: espacio.m,
  },
  heroTitulo: { fontSize: 20, fontWeight: "800", color: colores.tinta, marginTop: espacio.s },
  logo: { width: 200, height: 200, marginBottom: espacio.s },
  heroTexto: {
    fontSize: 13,
    color: colores.suave,
    textAlign: "center",
    marginTop: espacio.s,
    lineHeight: 19,
  },
  label: { fontSize: 13, fontWeight: "700", color: colores.texto, marginBottom: 6 },
  fila: { flexDirection: "row", flexWrap: "wrap", marginBottom: espacio.s },
  error: { color: colores.peligro, fontWeight: "600", marginBottom: espacio.s },
  tarjeta: {
    backgroundColor: colores.superficie,
    borderRadius: radio.m,
    borderWidth: 1,
    borderColor: colores.linea,
    padding: espacio.m,
    gap: espacio.m,
  },
  dato: { flexDirection: "row", alignItems: "center", gap: 8 },
  datoEtiqueta: { fontSize: 13, color: colores.suave, width: 140 },
  datoValor: { fontSize: 13, color: colores.tinta, fontWeight: "600", flex: 1 },
});
