import React, { useMemo, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, TextInput, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import Ionicons from "@expo/vector-icons/Ionicons";
import { api, qs, API_URL, API_LOCAL } from "../api";
import { useZona } from "../Zona";
import { colores, espacio, radio } from "../theme";
import { Btn, Chip, Encabezado, FilaChips, Vacio, Cargando } from "../ui";
import Tarjeta from "../Tarjeta";
import Pantalla from "../Pantalla";

const CATS = [
  "",
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

const ORDENES = [
  { value: "cercania", label: "Cerca" },
  { value: "reciente", label: "Reciente" },
  { value: "vistos", label: "Top" },
];

export default function Local({ navigation }) {
  const { zona, ref } = useZona();
  const [tipo, setTipo] = useState("");
  const [cat, setCat] = useState("");
  const [orden, setOrden] = useState("cercania");
  const [q, setQ] = useState("");

  const params = qs({ limit: 30, orden, tipo, categoria: cat, lat: ref[0], lng: ref[1] });

  const { data, isLoading, isRefetching, refetch } = useQuery({
    queryKey: ["lista", tipo, cat, orden, ref[0], ref[1]],
    queryFn: () => api.get(`/api/publicaciones${params}`),
  });

  const items = useMemo(() => {
    let lista = (data?.items || []).filter((p) => !String(p.tipo || "").startsWith("favor"));
    const s = q.trim().toLowerCase();
    if (s) lista = lista.filter((p) => `${p.titulo} ${p.descripcion}`.toLowerCase().includes(s));
    return lista;
  }, [data, q]);

  const cabecera = (
    <View>
      <Encabezado
        titulo="Economía Local"
        subtitulo={`Servicios y productos en ${zona}`}
        accion={
          <Btn icon="add" onPress={() => navigation.navigate("Publicar", { modo: "servicio" })}>
            Publicar
          </Btn>
        }
      />

      <View style={estilos.buscador}>
        <Ionicons name="search-outline" size={18} color={colores.suave} />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Buscar en tu sector…"
          placeholderTextColor={colores.suave}
          style={estilos.input}
          returnKeyType="search"
        />
      </View>

      {API_LOCAL ? (
        <View style={estilos.avisoApi}>
          <Ionicons name="wifi-outline" size={16} color={colores.aviso} />
          <Text style={estilos.avisoApiTexto}>
            API en {API_URL}. Desde el teléfono no funcionará: usa la URL del túnel en
            EXPO_PUBLIC_API_URL.
          </Text>
        </View>
      ) : null}

      <FilaChips>
        <Chip label="Todo" activo={tipo === ""} onPress={() => setTipo("")} />
        <Chip label="Servicios" activo={tipo === "servicio"} onPress={() => setTipo("servicio")} />
        <Chip label="Productos" activo={tipo === "producto"} onPress={() => setTipo("producto")} />
      </FilaChips>

      <FilaChips>
        {ORDENES.map((o) => (
          <Chip key={o.value} label={o.label} activo={orden === o.value} onPress={() => setOrden(o.value)} />
        ))}
      </FilaChips>

      <FilaChips>
        {CATS.map((c) => (
          <Chip key={c || "todas"} label={c || "Todas"} activo={cat === c} onPress={() => setCat(c)} />
        ))}
      </FilaChips>

      <Text style={estilos.hint}>
        {items.length} {tipo === "servicio" ? "servicios" : tipo === "producto" ? "productos" : "publicaciones"} en {zona}
      </Text>
    </View>
  );

  if (isLoading)
    return (
      <Pantalla>
        <Cargando />
      </Pantalla>
    );

  return (
    <Pantalla>
      <FlatList
        data={items}
        keyExtractor={(p) => p.id}
        contentContainerStyle={{ padding: espacio.l, paddingBottom: espacio.xl * 2 }}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colores.marca} />
        }
        ListHeaderComponent={cabecera}
        ListEmptyComponent={
          <Vacio
            titulo="No hay publicaciones con ese filtro"
            texto="Prueba con otra categoría o publica tú el primero."
            accion={<Btn onPress={() => navigation.navigate("Publicar", { modo: "servicio" })}>Publicar</Btn>}
          />
        }
        renderItem={({ item }) => (
          <Tarjeta p={item} zona={zona} onPress={() => navigation.navigate("Detalle", { id: item.id })} />
        )}
      />
    </Pantalla>
  );
}

const estilos = StyleSheet.create({
  buscador: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colores.superficie,
    borderWidth: 1,
    borderColor: colores.linea,
    borderRadius: radio.s,
    paddingHorizontal: espacio.m,
    height: 46,
    marginBottom: espacio.m,
  },
  input: { flex: 1, fontSize: 15, color: colores.tinta },
  fila: { flexDirection: "row", flexWrap: "wrap" },
  hint: { fontSize: 12, color: colores.suave, marginBottom: espacio.s },
  avisoApi: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    backgroundColor: colores.avisoSuave,
    borderRadius: radio.s,
    padding: espacio.s,
    marginBottom: espacio.m,
  },
  avisoApiTexto: { flex: 1, fontSize: 11, color: colores.aviso },
});
