# LiveSync Component - Integration Guide

## Overview

`UArchLiveSyncComponent` provides real-time WebSocket communication between the UE5 3D viewer and external 2D CAD/editor applications.

**Status:** Ready for integration with new 2D CAD software (Dec 2025)

---

## Features

| Feature | Description |
|---------|-------------|
| Auto-connect | Connects on BeginPlay if `bAutoConnect` is true |
| Auto-reconnect | Reconnects on disconnect with configurable interval |
| Protocol detection | Auto-detects Legacy (raw JSON) vs V1 (structured envelope) |
| Heartbeat | Keep-alive with latency tracking |
| Message queue | Priority-based queue when disconnected, drains on reconnect |
| Diagnostics | Connection stats, message counts, latency metrics |
| Bi-directional | Send selection/view changes back to CAD app |

---

## CAD Application Requirements

### Minimal Integration (Legacy Protocol)

1. **WebSocket Server** - Listen on `ws://localhost:8765` (or configure `ServerUrl` property)
2. **Send Building JSON** - Send raw building JSON on connection and on changes:
   ```json
   {
     "walls_batch": [...],
     "levels": [...],
     "doors": [...],
     "windows": [...],
     "roofs": [...]
   }
   ```
3. That's it - the component auto-detects Legacy protocol and updates the building

### Full Integration (V1 Protocol)

For bi-directional sync, implement structured message envelope:

```json
{
  "type": "building_data",
  "payload": { ... building JSON ... },
  "timestamp": 1703347200000,
  "full_sync": true
}
```

**Message Types:**

| Type | Direction | Description |
|------|-----------|-------------|
| `building_data` | CAD → UE5 | Full building JSON |
| `building_delta` | CAD → UE5 | Incremental update (future) |
| `selection` | Both | Selected element IDs |
| `view` | UE5 → CAD | Camera position/rotation |
| `heartbeat` | Both | Keep-alive ping |
| `heartbeat_ack` | Both | Heartbeat response |
| `error` | Both | Error messages |

**Selection Sync Example:**
```json
{
  "type": "selection",
  "payload": {
    "selected_ids": ["wall_001", "door_003"],
    "source": "editor"
  }
}
```

---

## UE5 Component Properties

### Connection
- `ServerUrl` - WebSocket URL (default: `ws://localhost:8765`)
- `bAutoConnect` - Connect on BeginPlay (default: true)
- `bAutoReconnect` - Reconnect on disconnect (default: true)
- `ReconnectInterval` - Seconds between attempts (default: 2.0)
- `MaxReconnectAttempts` - 0 = unlimited (default: 0)

### Heartbeat
- `bEnableHeartbeat` - Enable keep-alive (default: true)
- `HeartbeatInterval` - Seconds between pings (default: 5.0)
- `HeartbeatTimeout` - Seconds before disconnect (default: 15.0)

### Queue
- `MaxQueueSize` - Max queued messages (default: 100)
- `MaxQueueAge` - Drop messages older than N seconds (default: 60.0)

### Behavior
- `bAutoUpdateBuilding` - Auto-update ArchBuildingActor (default: true)
- `bLogMessages` - Log received messages (default: false)

---

## Blueprint Events (Delegates)

| Delegate | Parameter | Description |
|----------|-----------|-------------|
| `OnBuildingDataReceived` | `FString JsonData` | Legacy - raw building JSON |
| `OnConnectionStateChanged` | `EArchLiveSyncConnectionState` | State changes |
| `OnMessageReceived` | `FArchLiveSyncMessage` | Any parsed message |
| `OnSelectionChanged` | `FArchLiveSyncSelection` | Selection from CAD |
| `OnError` | `FString ErrorMessage` | Error events |
| `OnHeartbeatReceived` | - | Heartbeat received |

---

## Blueprint Methods

```cpp
// Connection
void Connect();
void Disconnect();
bool IsConnected();
EArchLiveSyncConnectionState GetConnectionState();

// Sending
void SendMessage(FString Message);
void SendTypedMessage(EArchLiveSyncMessageType Type, FString Payload, int32 Priority);
void SendSelectionChanged(TArray<FString> SelectedIds);
void SendViewChanged(FVector Location, FRotator Rotation);

// Diagnostics
FArchLiveSyncDiagnostics GetDiagnostics();
void ResetDiagnostics();

// Queue
void ClearOutgoingQueue();
int32 GetOutgoingQueueSize();
```

---

## Testing Checklist

- [ ] CAD server starts, UE5 auto-connects
- [ ] Building JSON received and rendered correctly
- [ ] Disconnect CAD → UE5 shows reconnection attempts
- [ ] Restart CAD → UE5 reconnects and resumes updates
- [ ] `GetDiagnostics()` returns accurate stats
- [ ] `OnConnectionStateChanged` fires on state transitions
- [ ] Selection sync works bi-directionally (V1 protocol)
- [ ] Heartbeat timeout triggers reconnect (V1 protocol)

---

## Files

| File | Description |
|------|-------------|
| `ArchLiveSyncTypes.h` | Enums and structs for protocol |
| `ArchLiveSyncComponent.h` | Component header |
| `ArchLiveSyncComponent.cpp` | Full implementation (~850 LOC) |

---

## Notes

- Component is backwards-compatible with existing Python 2D editor
- Legacy protocol: server ignores heartbeat pings (no response expected)
- V1 protocol: full heartbeat handshake with latency tracking
- Queue persists messages during disconnect, processes on reconnect
