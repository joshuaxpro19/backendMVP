import React from "react";
import { SafeAreaView } from "react-native-safe-area-context";
import { colores } from "./theme";

/** Envoltorio de pantalla que respeta el notch / barra de estado. */
export default function Pantalla({ children, style, edges = ["top"] }) {
  return (
    <SafeAreaView
      edges={edges}
      style={[{ flex: 1, backgroundColor: colores.fondo }, style]}
    >
      {children}
    </SafeAreaView>
  );
}
