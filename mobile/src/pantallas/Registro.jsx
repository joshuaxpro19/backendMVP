import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useAuth } from "../Auth";
import { useZona } from "../Zona";
import { colores, espacio } from "../theme";
import { Btn, Campo, Chip, Encabezado, FilaChips } from "../ui";
import Pantalla from "../Pantalla";

export default function Registro({ navigation }) {
  const { registrar } = useAuth();
  const { zonas } = useZona();

  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [zona, setZona] = useState("Piura Centro");
  const [yape, setYape] = useState("");
  const [plin, setPlin] = useState("");
  const [password, setPassword] = useState("");
  const [acepta, setAcepta] = useState(true);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  const enviar = async () => {
    setError("");
    if (nombre.trim().length < 3) return setError("Escribe tu nombre y apellido.");
    if (!/^\d{9}$/.test(telefono)) return setError("El celular debe tener 9 dígitos.");
    if (!/^\d{6,}$/.test(password)) return setError("La contraseña debe tener 6 dígitos o más.");
    if (!acepta) return setError("Debes aceptar el aviso de privacidad.");

    setCargando(true);
    try {
      await registrar({
        nombre: nombre.trim(),
        telefono,
        password,
        zona,
        yape,
        plin,
        acepta_privacidad: true,
      });
      navigation.goBack();
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <Pantalla>
      <ScrollView contentContainerStyle={estilos.cuerpo} keyboardShouldPersistTaps="handled">
        <Encabezado
          titulo="Crear cuenta"
          subtitulo="Solo vecinos del barrio"
          accion={
            <Pressable onPress={() => navigation.goBack()} hitSlop={12} accessibilityLabel="Cerrar">
              <Ionicons name="close" size={26} color={colores.tinta} />
            </Pressable>
          }
        />

        <Campo label="Nombre y apellido" value={nombre} onChangeText={setNombre} placeholder="Ana Paredes" />
        <Campo
          label="Celular (9 dígitos)"
          value={telefono}
          onChangeText={(v) => setTelefono(v.replace(/\D/g, ""))}
          keyboardType="phone-pad"
          maxLength={9}
          placeholder="987654321"
        />

        <Text style={estilos.label}>Sector donde vives</Text>
        <FilaChips>
          {zonas.map((z) => (
            <Chip key={z.nombre} label={z.nombre} activo={zona === z.nombre} onPress={() => setZona(z.nombre)} />
          ))}
        </FilaChips>

        <Campo
          label="Yape (opcional)"
          value={yape}
          onChangeText={(v) => setYape(v.replace(/\D/g, ""))}
          keyboardType="phone-pad"
          maxLength={9}
        />
        <Campo
          label="Plin (opcional)"
          value={plin}
          onChangeText={(v) => setPlin(v.replace(/\D/g, ""))}
          keyboardType="phone-pad"
          maxLength={9}
        />
        <Campo
          label="Contraseña (solo números, mínimo 6)"
          value={password}
          onChangeText={(v) => setPassword(v.replace(/\D/g, ""))}
          keyboardType="number-pad"
          secureTextEntry
          placeholder="••••••"
        />

        <View style={estilos.acepta}>
          <Switch value={acepta} onValueChange={setAcepta} trackColor={{ true: colores.marca }} />
          <Text style={estilos.aceptaTexto}>
            Acepto el aviso de privacidad y que mi celular solo lo vean vecinos con sesión.
          </Text>
        </View>

        {error ? <Text style={estilos.error}>{error}</Text> : null}

        <Btn onPress={enviar} disabled={cargando}>
          {cargando ? "Creando…" : "Crear cuenta"}
        </Btn>

        <Btn variant="fantasma" onPress={() => navigation.replace("Entrar")}>
          ¿Ya tienes cuenta? Iniciar sesión
        </Btn>
      </ScrollView>
    </Pantalla>
  );
}

const estilos = StyleSheet.create({
  cuerpo: { padding: espacio.l, paddingBottom: espacio.xl * 2 },
  label: { fontSize: 13, fontWeight: "700", color: colores.texto, marginBottom: 6 },
  acepta: { flexDirection: "row", alignItems: "center", gap: espacio.s, marginVertical: espacio.m },
  aceptaTexto: { flex: 1, fontSize: 12, color: colores.suave },
  error: { color: colores.peligro, fontWeight: "600", marginBottom: espacio.s },
});
