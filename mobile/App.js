import React from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { SafeAreaProvider } from "react-native-safe-area-context";
import Ionicons from "@expo/vector-icons/Ionicons";

import { AuthProvider } from "./src/Auth";
import { ZonaProvider } from "./src/Zona";
import { colores } from "./src/theme";

import Local from "./src/pantallas/Local";
import Favores from "./src/pantallas/Favores";
import Emergencia from "./src/pantallas/Emergencia";
import Actividad from "./src/pantallas/Actividad";
import Perfil from "./src/pantallas/Perfil";
import Tutorial from "./src/pantallas/Tutorial";
import Entrar from "./src/pantallas/Entrar";
import Registro from "./src/pantallas/Registro";
import Ia from "./src/pantallas/Ia";
import Detalle from "./src/Detalle";
import Publicar from "./src/Publicar";

const Tabs = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
  },
});

const ICONOS = {
  Local: "storefront-outline",
  Favores: "hand-left-outline",
  Emergencia: "warning-outline",
  Actividad: "list-outline",
  Perfil: "person-outline",
};

// Color de la sección cuando la pestaña está activa.
const COLOR_SECCION = {
  Local: "#1b7f4b",      // verde
  Favores: "#1565C0",    // azul
  Emergencia: "#b61722", // rojo
  Actividad: "#1b7f4b",  // verde
  Perfil: "#1b7f4b",     // verde
};

function TabsPrincipales() {
  const insets = useSafeAreaInsets();
  return (
    <Tabs.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: COLOR_SECCION[route.name] || colores.marca,
        tabBarInactiveTintColor: colores.suave,
        tabBarStyle: {
          backgroundColor: colores.superficie,
          borderTopColor: colores.linea,
          height: 58 + insets.bottom,
          paddingBottom: insets.bottom > 0 ? insets.bottom : 8,
          paddingTop: 4,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
        tabBarIcon: ({ color, size }) => (
          <Ionicons name={ICONOS[route.name]} size={size} color={color} />
        ),
      })}
    >
      <Tabs.Screen name="Local" component={Local} options={{ title: "Local" }} />
      <Tabs.Screen name="Favores" component={Favores} options={{ title: "Favores" }} />
      <Tabs.Screen name="Emergencia" component={Emergencia} options={{ title: "Emergencia" }} />
      <Tabs.Screen name="Actividad" component={Actividad} options={{ title: "Actividad" }} />
      <Tabs.Screen name="Perfil" component={Perfil} options={{ title: "Perfil" }} />
    </Tabs.Navigator>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ZonaProvider>
            <NavigationContainer>
              <StatusBar style="dark" />
              <Stack.Navigator screenOptions={{ headerShown: false }}>
                <Stack.Screen name="Tabs" component={TabsPrincipales} />
                <Stack.Screen name="Detalle" component={Detalle} options={{ presentation: "card" }} />
                <Stack.Screen name="Publicar" component={Publicar} options={{ presentation: "modal" }} />
                <Stack.Screen name="Entrar" component={Entrar} options={{ presentation: "modal" }} />
                <Stack.Screen name="Registro" component={Registro} options={{ presentation: "modal" }} />
                <Stack.Screen name="Ia" component={Ia} options={{ presentation: "modal" }} />
                <Stack.Screen name="Tutorial" component={Tutorial} options={{ presentation: "modal" }} />
              </Stack.Navigator>
            </NavigationContainer>
          </ZonaProvider>
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
