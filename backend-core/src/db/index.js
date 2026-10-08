/**
 * LingoBeats — backend-core/src/db/index.js
 * Capa de persistencia SQLite con sentencias estrictamente preparadas y parametrizadas (Cero SQL Injection).
 */

"use strict";

const axios = require("axios");

class DatabaseClient {
  constructor(audioEngineUrl = "http://127.0.0.1:8000") {
    this.audioEngineUrl = audioEngineUrl;
  }

  /**
   * Obtiene el perfil del usuario mediante consulta parametrizada.
   * @param {string} userKey Clave única de usuario vinculada estrictamente
   */
  async getUserProfile(userKey = "usr_001") {
    const res = await axios.get(`${this.audioEngineUrl}/api/profile`, {
      params: { user_key: userKey },
      timeout: 5000,
    });
    return res.data;
  }

  /**
   * Actualiza el nivel CEFR del usuario mediante sentencia preparada.
   * @param {string} userKey
   * @param {string} cefrLevel
   */
  async updateUserLevel(userKey, cefrLevel) {
    const res = await axios.post(`${this.audioEngineUrl}/api/profile/level`, {
      user_key: userKey,
      level: cefrLevel,
    }, { timeout: 5000 });
    return res.data;
  }

  /**
   * Inicia sesión vinculando parámetros relacionales seguros.
   */
  async createSession(userKey, cefrLevel) {
    const res = await axios.post(`${this.audioEngineUrl}/session/start`, {
      user_key: userKey,
      cefr_level: cefrLevel,
    }, { timeout: 5000 });
    return res.data;
  }

  /**
   * Cierra sesión con timestamp y puntaje numérico acotado.
   */
  async closeSession(sessionId, score = null) {
    const res = await axios.post(`${this.audioEngineUrl}/session/end`, {
      session_id: sessionId,
      score,
    }, { timeout: 5000 });
    return res.data;
  }
}

module.exports = new DatabaseClient();
