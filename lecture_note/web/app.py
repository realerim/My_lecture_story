"""녹화/캡처가 진행 중이어도 지금까지의 노트를 실시간으로 확인할 수 있는 로컬 웹뷰어.

record 명령이 백그라운드로 돌아가는 동안 이 서버를 같이 띄워두면, 화면이 바뀔 때마다
새 섹션이 즉시 추가되는 것을 브라우저에서 볼 수 있다 (몇 초 간격 폴링).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lecture_note import session as session_mod
from lecture_note.notes.builder import build_sections
from lecture_note.notes.markdown_writer import fmt_ts

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Lecture Note Viewer")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

session_mod.DATA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(session_mod.DATA_ROOT)), name="files")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _get_session_or_404(session_id: str) -> session_mod.Session:
    s = session_mod.Session(session_id)
    if not s.root.exists():
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    return s


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    items = []
    for s in session_mod.list_sessions():
        meta = s.read_meta()
        items.append(
            {
                "id": s.session_id,
                "title": meta.get("title", s.session_id),
                "mode": meta.get("mode", "record"),
                "has_notes": s.notes_path.exists(),
            }
        )
    return templates.TemplateResponse(request, "index.html", {"sessions": items})


@app.get("/session/{session_id}", response_class=HTMLResponse)
def session_page(request: Request, session_id: str):
    s = _get_session_or_404(session_id)
    meta = s.read_meta()
    return templates.TemplateResponse(
        request,
        "session.html",
        {"session_id": session_id, "title": meta.get("title", session_id)},
    )


@app.get("/session/{session_id}/data")
def session_data(session_id: str):
    s = _get_session_or_404(session_id)
    sections = build_sections(s.read_screen_events(), s.read_transcript_segments())
    organized = s.read_organized()

    return {
        "session_id": session_id,
        "finalized": s.notes_path.exists(),
        "sections": [
            {
                "index": sec.index,
                "time_label": fmt_ts(sec.start) + (f" ~ {fmt_ts(sec.end)}" if sec.end is not None else ""),
                "image_url": f"/files/{session_id}/{sec.image}" if sec.image else None,
                "text": organized.get(sec.index) or sec.raw_text or "(아직 음성 내용이 인식되지 않았습니다)",
                "organized": sec.index in organized,
            }
            for sec in sections
        ],
    }


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
