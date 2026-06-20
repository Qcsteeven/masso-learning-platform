import json

from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["websocket"])
async def _stub_ws(ws: WebSocket, msg: str) -> None:
    await ws.accept()
    await ws.send_text(json.dumps({"type": "error", "message": msg}))
    await ws.close()
@router.websocket("/ws/sessions/{session_id}/terminal")
async def ws_terminal(session_id: str, ws: WebSocket) -> None:
    await _stub_ws(ws, "Terminal not yet implemented")
@router.websocket("/ws/sessions/{session_id}/events")
async def ws_events(session_id: str, ws: WebSocket) -> None:
    await _stub_ws(ws, "Events not yet implemented")
@router.websocket("/ws/sessions/{session_id}/status")
async def ws_status(session_id: str, ws: WebSocket) -> None:
    await _stub_ws(ws, "Status not yet implemented")
@router.websocket("/ws/admin/monitoring")
async def ws_monitoring(ws: WebSocket) -> None:
    await _stub_ws(ws, "Monitoring not yet implemented")
