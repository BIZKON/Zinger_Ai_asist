/**
 * VoxEngine скрипт для VoximPlant.
 * Загружается в VoximPlant Console.
 *
 * TODO: Реализация в Фазе 3
 *
 * Логика:
 *   1. VoxEngine.addEventListener(AppEvents.CallAlerting, ...)
 *   2. При Connected → создать WebSocket к wss://api.personalai.ru/voice/stream
 *   3. Bridge: call audio ↔ WebSocket
 */
