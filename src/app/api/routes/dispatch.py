from pathlib import Path
from datetime import datetime
import traceback
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.processo_service import ProcessoService

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])
bearer_scheme = HTTPBearer()

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "template"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


class DispatchPayload(BaseModel):
    setor_destino_sugerido: str = Field(..., min_length=1)
    assunto: str = Field(..., min_length=1)
    corpo_despacho: str = Field(..., min_length=1)
    referencias_normativas: list[str] = Field(default_factory=list)
    justificativa_encaminhamento: str = Field(..., min_length=0)
    status_sugerido: str = Field(..., min_length=1)
    processo_numero: str | None = None
    numero_despacho: str = "___/CPPD/2026"


def _get_user_attr(user, attr: str, default: str) -> str:
    return getattr(user, attr, default) if user else default

def _replace_dispatch_placeholders(text: str, replacements: dict[str, str]) -> str:
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text

def _build_dispatch_context(
    processo,
    *,
    setor_destino_sugerido: str,
    assunto: str,
    corpo_despacho: str,
    processo_numero: str | None = None,
    numero_despacho: str,
    emitido_em: str | None = None,
) -> dict:
    usuario = getattr(processo, "usuario", None)
    professor_nome = _get_user_attr(usuario, "nome", "N/A")
    professor_setor = _get_user_attr(usuario, "setor", "N/A")
    professor_matricula = _get_user_attr(usuario, "matricula", "N/A")
    numero_processo = processo_numero or getattr(processo, "numero", "")
    emitido_em = emitido_em or datetime.utcnow().strftime("%d/%m/%Y")

    corpo_despacho = _replace_dispatch_placeholders(
        corpo_despacho,
        {
            "[numero_processo]": numero_processo,
            "[nome_requerente]": professor_nome,
            "[cargo]": _get_user_attr(usuario, "cargo", ""),
            "[matricula]": professor_matricula,
            "[lotacao]": professor_setor,
            "[AUTORIDADE]": setor_destino_sugerido,
            "[DATA_ATUAL]": emitido_em,
        },
    )

    return {
        "processo_numero": numero_processo,
        "setor_destino_sugerido": setor_destino_sugerido,
        "assunto": assunto,
        "professor_nome": professor_nome,
        "professor_setor": professor_setor,
        "professor_matricula": professor_matricula,
        "emitido_em": emitido_em,
        "corpo_despacho": corpo_despacho,
        "numero_despacho": numero_despacho,
    }

def _render_dispatch_html(context: dict) -> str:
    return templates.env.get_template("dispatch.html").render(context)

def _generate_pdf(html: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()


@router.post("/pdf-preview/{processo_id}")
async def pdf_preview(
    processo_id: UUID,
    payload: DispatchPayload,
    db: AsyncSession = Depends(get_db),
):
    """Gera um PDF temporário do despacho para visualização no frontend."""
    processo = await ProcessoService.get_processo(db=db, processo_id=str(processo_id))
    if not processo:
        raise HTTPException(status_code=404, detail="Processo não encontrado")

    usuario = getattr(processo, 'usuario', None)
    
    # Substitui placeholders no corpo do despacho
    corpo_despacho = payload.corpo_despacho
    replacements = {
        "[numero_processo]": processo.numero,
        "[nome_requerente]": _get_user_attr(usuario, 'nome', 'N/A'),
        "[cargo]": _get_user_attr(usuario, 'cargo', 'N/A'),
        "[matricula]": _get_user_attr(usuario, 'matricula', 'N/A'),
        "[lotacao]": _get_user_attr(usuario, 'setor', 'N/A'),
        "[AUTORIDADE]": payload.setor_destino_sugerido,
        "[DATA_ATUAL]": datetime.utcnow().strftime('%d/%m/%Y'),
    }
    for p, v in replacements.items():
        corpo_despacho = corpo_despacho.replace(p, v)

    # Usa os dados vindos do payload (editados no frontend)
    context = {
        "processo_numero": payload.processo_numero or processo.numero,
        "setor_destino_sugerido": payload.setor_destino_sugerido,
        "assunto": payload.assunto,
        "professor_nome": _get_user_attr(usuario, 'nome', 'N/A'),
        "professor_setor": _get_user_attr(usuario, 'setor', 'N/A'),
        "professor_matricula": _get_user_attr(usuario, 'matricula', 'N/A'),
        "emitido_em": datetime.utcnow().strftime('%d/%m/%Y'),
        "corpo_despacho": corpo_despacho,
        "numero_despacho": payload.numero_despacho or "PREVIEW/2026"
    }

    try:
        html = _render_dispatch_html(context)
        pdf_bytes = _generate_pdf(html)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=preview_despacho.pdf"}
        )
    except Exception as e:
        print(f"[PDF PREVIEW] Erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview", response_class=HTMLResponse)
async def render_preview(request: Request, payload: DispatchPayload):
    context = payload.model_dump()
    context.update({
        "request": request,
        "processo_numero": payload.processo_numero or "",
    })
    return templates.TemplateResponse(request=request, name="dispatch.html", context=context)


@router.post("/send/{processo_id}")
async def send_despacho_to_processo(
    processo_id: UUID,
    payload: DispatchPayload,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """Renderiza o despacho como HTML e salva como documento do processo.

    Apenas usuários com role 'avaliador' podem enviar o despacho via esta rota.
    """
    user = await get_current_user(token.credentials, db)
    if not user or getattr(user, "role", None) != "avaliador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão negada: apenas avaliadores podem enviar despacho",
        )

    processo = await ProcessoService.get_processo(db=db, processo_id=str(processo_id))
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado",
        )

    usuario = getattr(processo, 'usuario', None)
    context = payload.model_dump()
    
    context.update({
        "request": {},
        "processo_numero": payload.processo_numero or processo.numero,
        "professor_nome": _get_user_attr(usuario, 'nome', ''),
        "professor_setor": _get_user_attr(usuario, 'setor', ''),
        "professor_matricula": _get_user_attr(usuario, 'matricula', ''),
        "emitido_em": datetime.utcnow().strftime('%d/%m/%Y'),
    })
    
    try:
        html = _render_dispatch_html(context)
    except Exception:
        print(f"[DISPATCH SEND] Erro ao renderizar template:\n{traceback.format_exc()}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao renderizar template. Verifique os logs do servidor.",
        )

    try:
        try:
            pdf_bytes = _generate_pdf(html)
            filename = f"Despacho_{processo.numero}.pdf"
            documento = await ProcessoService.save_documento(
                db=db,
                processo_id=str(processo_id),
                tipo_doc="despacho_pdf",
                arquivo_bytes=pdf_bytes,
                name_arquivo=filename,
            )
        except ModuleNotFoundError:
            # WeasyPrint não disponível: salva HTML como fallback
            filename = f"despacho_{processo.numero}.html"
            documento = await ProcessoService.save_documento(
                db=db,
                processo_id=str(processo_id),
                tipo_doc="despacho_html",
                arquivo_bytes=html.encode("utf-8"),
                name_arquivo=filename,
            )
    except Exception:
        print(f"[DISPATCH SEND] Erro ao gerar/salvar despacho:\n{traceback.format_exc()}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar ou salvar o despacho. Verifique os logs do servidor.",
        )

    # Salva também texto do despacho no campo do processo
    await ProcessoService.save_despacho_automatico(db=db, processo_id=str(processo_id), despacho=payload.corpo_despacho)
    await db.commit()

    # Garantir serialização JSON correta (UUID -> string)
    try:
        doc_id = str(documento.id)
    except Exception:
        doc_id = documento.id

    print(f"[DISPATCH SEND] Documento salvo: id={doc_id}, caminho={documento.caminho_arquivo}", flush=True)

    return JSONResponse({
        "ok": True,
        "documento_id": doc_id,
        "caminho": documento.caminho_arquivo,
        "processo_numero": payload.processo_numero or processo.numero,
    })