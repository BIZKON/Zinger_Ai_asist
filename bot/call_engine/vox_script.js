/**
 * VoxEngine скрипт для VoximPlant.
 * Загружается в VoximPlant Console → Applications → Rules → Scripts.
 *
 * Логика:
 *   1. Получаем входящий/исходящий звонок
 *   2. Устанавливаем WebSocket соединение с PersonalAI Voice Engine
 *   3. Передаём аудио в обе стороны: звонок ↔ WebSocket
 *   4. При завершении — закрываем соединение
 *
 * Настройки (VoximPlant Application Config):
 *   WS_URL — URL WebSocket сервера (wss://api.personalai.ru/voice/stream)
 *   USER_ID — UUID пользователя для контекста
 *   USER_NAME — имя пользователя
 */

const WS_URL = VoxEngine.customData()
  ? JSON.parse(VoxEngine.customData()).ws_url
  : "wss://api.personalai.ru/voice/stream";

let call = null;
let ws = null;

// ── Исходящий звонок (Сценарий A: ручной / B: авто-обзвон) ──

VoxEngine.addEventListener(AppEvents.CallAlerting, function (e) {
  call = e.call;

  // Получаем параметры из customData
  let params = {};
  try {
    params = JSON.parse(VoxEngine.customData() || "{}");
  } catch (err) {
    Logger.write("Failed to parse customData: " + err);
  }

  call.addEventListener(CallEvents.Connected, function () {
    Logger.write("Call connected, opening WebSocket...");

    ws = VoxEngine.createWebSocket(WS_URL);

    ws.addEventListener(WebSocketEvents.OPENED, function () {
      Logger.write("WebSocket opened");

      // Send start message with call context
      ws.send(JSON.stringify({
        type: "start",
        user_id: params.user_id || "",
        user_name: params.user_name || "",
        contact_name: params.contact_name || "",
        contact_phone: call.number() || "",
        script_type: params.script_type || "manual",
        context: params.context || ""
      }));
    });

    ws.addEventListener(WebSocketEvents.MESSAGE, function (e) {
      try {
        const msg = JSON.parse(e.text);

        if (msg.type === "greeting" || msg.type === "response") {
          if (msg.audio) {
            // Play TTS audio to the call
            const player = VoxEngine.createURLPlayer(
              "data:audio/mpeg;base64," + msg.audio
            );
            player.sendMediaTo(call);
            player.addEventListener(PlayerEvents.PlaybackFinished, function () {
              player.stop();
            });
          }
        } else if (msg.type === "end") {
          Logger.write("Call ended by AI. Summary: " + msg.summary);
          call.hangup();
        }
      } catch (err) {
        Logger.write("Message parse error: " + err);
      }
    });

    ws.addEventListener(WebSocketEvents.ERROR, function (e) {
      Logger.write("WebSocket error: " + e.reason);
    });

    ws.addEventListener(WebSocketEvents.CLOSED, function () {
      Logger.write("WebSocket closed");
    });

    // Bridge call audio → WebSocket (PCM 16kHz)
    call.sendMediaTo(ws);
  });

  call.addEventListener(CallEvents.Disconnected, function () {
    Logger.write("Call disconnected");

    if (ws) {
      ws.send(JSON.stringify({
        type: "end",
        direction: "outbound",
        contact_phone: call.number() || "",
        outcome: "completed"
      }));
      ws.close();
    }

    VoxEngine.terminate();
  });

  call.addEventListener(CallEvents.Failed, function (e) {
    Logger.write("Call failed: " + e.reason);

    if (ws) {
      ws.send(JSON.stringify({
        type: "end",
        outcome: "no_answer"
      }));
      ws.close();
    }

    VoxEngine.terminate();
  });

  // Answer the call
  call.answer();
});

// ── Входящий звонок (Сценарий C: входящая линия) ──

VoxEngine.addEventListener(AppEvents.CallAlerting, function (e) {
  if (e.call.incoming()) {
    call = e.call;

    call.addEventListener(CallEvents.Connected, function () {
      Logger.write("Incoming call connected");

      ws = VoxEngine.createWebSocket(WS_URL);

      ws.addEventListener(WebSocketEvents.OPENED, function () {
        ws.send(JSON.stringify({
          type: "start",
          user_id: "",  // Will be resolved by server from phone number
          contact_phone: call.callerid() || "",
          script_type: "inbound",
          context: "Входящий звонок на номер Зингер Логистика"
        }));
      });

      // Same message/audio handling as outbound
      ws.addEventListener(WebSocketEvents.MESSAGE, function (e) {
        try {
          const msg = JSON.parse(e.text);
          if ((msg.type === "greeting" || msg.type === "response") && msg.audio) {
            const player = VoxEngine.createURLPlayer(
              "data:audio/mpeg;base64," + msg.audio
            );
            player.sendMediaTo(call);
            player.addEventListener(PlayerEvents.PlaybackFinished, function () {
              player.stop();
            });
          }
        } catch (err) {
          Logger.write("Parse error: " + err);
        }
      });

      call.sendMediaTo(ws);
    });

    call.addEventListener(CallEvents.Disconnected, function () {
      if (ws) {
        ws.send(JSON.stringify({ type: "end", outcome: "completed" }));
        ws.close();
      }
      VoxEngine.terminate();
    });

    call.answer();
  }
});
