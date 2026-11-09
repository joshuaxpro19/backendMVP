import React, { useMemo, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, TextInput, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import Ionicons from "@expo/vector-icons/Ionicons";
import { api, qs } from "../api";
import { useZona } from "../Zona";
import { colores, espacio, radio } from "../theme";
import { Btn, Chip, Encabezado, FilaChips, Vacio, Cargando } from "../ui";
import Tarjeta from "../Tarjeta";
import Pantalla from "../Pantalla";

const FILTROS = [
  { value: "", label: "Todos" },
  { value: "favor_solicitado", label: "Necesito" },
  { value: "favor_ofrecido", label: "Ofrezco" },
];

const SUBTIPOS = [
  { value: "", label: "Todo" },
  { value: "prestamo", label: "Préstamo" },
  { value: "ayuda_temporal", label: "Ayuda" },
  { value: "donacion", label: "Donación" },
  { value: "intercambio_habilidades", label: "Habilidades" },
  { value: "movilidad", label: "Movilidad" },
];

export default function Favores({ navigation }) {
  const { zona, ref } = useZona();
  const [filtro, setFiltro] = useState("");
  const [subtipo, setSubtipo] = useState("");
  const [q, setQ] = useState("");

  const params = qs({
    limit: 50,
    solo_favores: "true",
    tipo: filtro,
    tipo_favor: subtipo,
    lat: ref[0],
    lng: ref[1],
  });

  const { data, isLoading, isRefetching, refetch } = useQuery({
    queryKey: ["favores", filtro, subtipo, ref[0], ref[1]],
    queryFn: () => api.get(`/api/publicaciones${params}`),
  });

  const items = useMemo(() => {
    let lista = data?.items || [];
    const s = q.trim().toLowerCase();
    if (s) lista = lista.filter((p) => `${p.titulo} ${p.descripcion}`.toLowerCase().includes(s));
    return lista;
  }, [data, q]);

  const cabecera = (
    <View>
      <Encabezado
        titulo="Economía Solidaria"
        subtitulo={`Favores entre vecinos de ${zona}`}
        accion={<Btn icon="add" onPress={() => navigation.navigate("Publicar", { modo: "favor" })}>Publicar</Btn>}
      />

      <View style={estilos.buscador}>
        <Ionicons name="search-outline" size={18} color={colores.suave} />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Buscar un favor…"
          placeholderTextColor={colores.suave}
          style={estilos.input}
        />
      </View>

      <FilaChips>
        {FILTROS.map((f) => (
          <Chip key={f.value || "todos"} label={f.label} activo={filtro === f.value} onPress={() => setFiltro(f.value)} />
        ))}
      </FilaChips>

      <FilaChips>
        {SUBTIPOS.map((s) => (
          <Chip key={s.value || "todo"} label={s.label} activo={subtipo === s.value} onPress={() => setSubtipo(s.value)} />
        ))}
      </FilaChips>

      <Text style={estilos.hint}>{items.length} favores en {zona}</Text>
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
            titulo="Sin favores por ahora"
            texto="Pide u ofrece ayuda: préstamos, donaciones, habilidades o movilidad."
            accion={<Btn onPress={() => navigation.navigate("Publicar", { modo: "favor" })}>Publicar</Btn>}
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
});
