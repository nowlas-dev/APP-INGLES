/**
 * LingoBeats Root Proxy Server Entrypoint
 * Reenvía la ejecución al orquestador en orchestrator/server.js
 */
process.chdir(__dirname + '/orchestrator');
require('./orchestrator/server.js');
