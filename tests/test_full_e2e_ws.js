const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

const audioPath = path.resolve(__dirname, '..', 'data', 'storage', 'turns', '1', 'turn_2_1791419446.webm');
const audioBuffer = fs.readFileSync(audioPath);

const ws = new WebSocket('ws://127.0.0.1:3000/ws');

ws.on('open', () => {
  console.log('[E2E TEST] WS connected to ws://127.0.0.1:3000/ws');
});

ws.on('message', (rawData, isBinary) => {
  if (isBinary) {
    console.log('[E2E TEST] Received binary frame, length:', rawData.length);
    return;
  }
  let str = typeof rawData === 'string' ? rawData : rawData.toString('utf8');
  let msg;
  try {
    msg = JSON.parse(str);
  } catch (err) {
    console.error('[E2E TEST] Failed to parse JSON:', err.message, 'Raw:', str.substring(0, 100));
    return;
  }

  console.log('[E2E TEST] Message received:', msg.type);

  if (msg.type === 'connected') {
    console.log('[E2E TEST] Session established: #' + msg.sessionId + '. Sending audio of size:', audioBuffer.length);
    ws.send(audioBuffer);
  } else if (msg.type === 'tutor_response') {
    console.log('[E2E TEST] ✅ SUCCESS! Tutor response received:');
    console.log('   - Transcript:', msg.transcript);
    console.log('   - Conversation:', msg.conversation);
    console.log('   - Feedback:', msg.feedback);
    console.log('   - Audio B64 Present:', !!msg.audio_b64);
    ws.close();
    process.exit(0);
  } else if (msg.type === 'error') {
    console.error('[E2E TEST] ❌ ERROR received:', msg.message);
    ws.close();
    process.exit(1);
  }
});

setTimeout(() => {
  console.error('[E2E TEST] ❌ Timeout after 25s');
  process.exit(1);
}, 25000);
