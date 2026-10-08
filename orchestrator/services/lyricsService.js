/**
 * LingoBeats — orchestrator/services/lyricsService.js
 * Cliente de integración con LRCLIB, parser de marcas de tiempo LRC y agregador de estrofas.
 */

"use strict";

const axios = require("axios");

class LyricsService {
  constructor(audioEngineUrl = "http://localhost:8000") {
    this.audioEngineUrl = audioEngineUrl;
    this.baseUrl = "https://lrclib.net/api";
    this.cache = new Map(); // Caché en memoria Nivel 1
  }

  /**
   * Convierte timestamp [mm:ss.xx] o [mm:ss.xxx] a segundos flotantes.
   * Ej: [01:12.45] -> 72.45
   */
  parseTimestamp(tag) {
    const match = tag.match(/\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\]/);
    if (!match) return null;

    const minutes = parseInt(match[1], 10);
    const seconds = parseInt(match[2], 10);
    const fraction = match[3] ? parseFloat(`0.${match[3]}`) : 0.0;

    return minutes * 60 + seconds + fraction;
  }

  /**
   * Parsea un texto crudo .lrc a un array ordenado de líneas con timestamps.
   */
  parseLRC(rawLrc) {
    if (!rawLrc) return [];

    const lines = rawLrc.split(/\r?\n/);
    const parsed = [];

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Líneas que contienen una o más marcas de tiempo
      const timeMatch = trimmed.match(/^\[\d{2}:\d{2}(?:\.\d{2,3})?\]/);
      if (!timeMatch) continue;

      const timeTag = timeMatch[0];
      const timeSec = this.parseTimestamp(timeTag);
      const text = trimmed.replace(/^\[\d{2}:\d{2}(?:\.\d{2,3})?\]\s*/, "").trim();

      if (timeSec !== null && text) {
        parsed.push({
          time: parseFloat(timeSec.toFixed(2)),
          text,
        });
      }
    }

    // Ordenar cronológicamente
    parsed.sort((a, b) => a.time - b.time);
    return parsed;
  }

  /**
   * Algoritmo de agrupación: une versos en estrofas lógicas (2 a 4 líneas)
   * basándose en pausas temporales > 2.5s entre versos consecutivos.
   */
  groupIntoStanzas(parsedLines) {
    if (!parsedLines || parsedLines.length === 0) return [];

    const stanzas = [];
    let currentStanzaLines = [];
    let stanzaId = 1;

    for (let i = 0; i < parsedLines.length; i++) {
      const currentLine = parsedLines[i];
      currentStanzaLines.push(currentLine);

      const nextLine = parsedLines[i + 1];
      const shouldCloseStanza =
        !nextLine || // Última línea
        currentStanzaLines.length >= 4 || // Máximo 4 líneas
        (nextLine.time - currentLine.time > 2.5 && currentStanzaLines.length >= 2); // Pausa > 2.5s

      if (shouldCloseStanza) {
        const startTime = currentStanzaLines[0].time;
        // end_time calculado a partir de la siguiente estrofa o duración estimada de la última línea
        let endTime = nextLine ? nextLine.time : currentLine.time + 3.5;
        if (endTime <= startTime) endTime = startTime + 3.0;

        stanzas.push({
          stanza_id: stanzaId++,
          start_time: parseFloat(startTime.toFixed(2)),
          end_time: parseFloat(endTime.toFixed(2)),
          lines: [...currentStanzaLines],
          text: currentStanzaLines.map((l) => l.text).join("\n"),
        });

        currentStanzaLines = [];
      }
    }

    return stanzas;
  }

  /**
   * Obtiene la letra sincronizada desde LRCLIB con fallback a búsqueda y caché local.
   */
  async getLyrics(trackName, artistName = "", albumName = "", duration = null) {
    const queryKey = `${(trackName || "").toLowerCase().trim()}::${(artistName || "").toLowerCase().trim()}`;

    // 1. Verificar caché en memoria
    if (this.cache.has(queryKey)) {
      console.log(`[LRCLIB] ⚡ Caché en memoria alcanzada para '${trackName}'`);
      return this.cache.get(queryKey);
    }

    let rawLrc = "";
    let trackTitle = trackName;
    let trackArtist = artistName;

    // 2. Consulta a /api/get
    try {
      const params = { track_name: trackName };
      if (artistName) params.artist_name = artistName;
      if (albumName) params.album_name = albumName;
      if (duration) params.duration = Math.round(duration);

      const res = await axios.get(`${this.baseUrl}/get`, {
        params,
        timeout: 6000,
        headers: { "User-Agent": "LingoBeats/2.0 (contact@lingobeats.app)" },
      });

      if (res.data && res.data.syncedLyrics) {
        rawLrc = res.data.syncedLyrics;
        trackTitle = res.data.trackName || trackTitle;
        trackArtist = res.data.artistName || trackArtist;
      }
    } catch (err) {
      console.warn(`[LRCLIB] /get no encontró coincidencia directa para '${trackName}'. Probando búsqueda de respaldo...`);
    }

    // 3. Fallback a /api/search
    if (!rawLrc) {
      try {
        const query = `${trackName} ${artistName}`.trim();
        const searchRes = await axios.get(`${this.baseUrl}/search`, {
          params: { q: query },
          timeout: 6000,
          headers: { "User-Agent": "LingoBeats/2.0 (contact@lingobeats.app)" },
        });

        const candidates = searchRes.data || [];
        const syncedCandidate = candidates.find((c) => c.syncedLyrics);

        if (syncedCandidate) {
          rawLrc = syncedCandidate.syncedLyrics;
          trackTitle = syncedCandidate.trackName || trackTitle;
          trackArtist = syncedCandidate.artistName || trackArtist;
        }
      } catch (searchErr) {
        console.error(`[LRCLIB] Error en búsqueda de letras: ${searchErr.message}`);
      }
    }

    if (!rawLrc) {
      return {
        found: false,
        track_name: trackName,
        artist_name: artistName,
        message: "No se encontraron letras sincronizadas para esta pista.",
        stanzas: [],
      };
    }

    // 4. Parsear y agrupar
    const parsedLines = this.parseLRC(rawLrc);
    const stanzas = this.groupIntoStanzas(parsedLines);

    const result = {
      found: true,
      query_key: queryKey,
      track_name: trackTitle,
      artist_name: trackArtist,
      raw_lrc: rawLrc,
      stanzas,
      total_stanzas: stanzas.length,
    };

    // Guardar en caché
    this.cache.set(queryKey, result);
    console.log(`[LRCLIB] ✅ Letras sincronizadas obtenidas: ${stanzas.length} estrofas para '${trackTitle}'`);

    return result;
  }
}

module.exports = new LyricsService();
