import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useAuth } from "../Auth";
import { colores, espacio } from "../theme";
import { Btn, Campo, Encabezado } from "../ui";
import Pantalla from "../Pantalla";

export default function Entrar({ navigation }) {
  const { entrar } = useAuth();
  const [telefono, setTelefono] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  const enviar = async () => {
    setError("");
    if (!/^\d{9}$/.test(telefono)) {
      setError("El celular debe tener 9 dígitos.");
      return;
    }
    setCargando(true);
    try {
      await entrar(telefono, password);
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
          titulo="Iniciar sesión"
          subtitulo="Entra con tu celular"
          accion={
            <Pressable onPress={() => navigation.goBack()} hitSlop={12} accessibilityLabel="Cerrar">
              <Ionicons name="close" size={26} color={colores.tinta} />
            </Pressable>
          }
        />

        <Campo
          label="Celular (9 dígitos)"
          value={telefono}
          onChangeText={(v) => setTelefono(v.replace(/\D/g, ""))}
          keyboardType="phone-pad"
          maxLength={9}
          placeholder="987654321"
        />
        <Campo
          label="Contraseña"
          value={password}
          onChangeText={(v) => setPassword(v.replace(/\D/g, ""))}
          keyboardType="number-pad"
          secureTextEntry
          placeholder="••••••"
        />

        {error ? <Text style={estilos.error}>{error}</Text> : null}

        <Btn onPress={enviar} disabled={cargando || !telefono || !password}>
          {cargando ? "Entrando…" : "Entrar"}
        </Btn>

        <Btn variant="fantasma" onPress={() => navigation.replace("Registro")}>
          ¿No tienes cuenta? Crear una
        </Btn>
      </ScrollView>
    </Pantalla>
  );
}

const estilos = StyleSheet.create({
  cuerpo: { padding: espacio.l, paddingBottom: espacio.xl * 2 },
  error: { color: colores.peligro, fontWeight: "600", marginBottom: espacio.s },
});
