from pathlib import Path
from datetime import datetime
import traceback
import sys
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

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[2] / "template")
)


class DispatchPayload(BaseModel):
    setor_destino_sugerido: str = Field(..., min_length=1)
    assunto: str = Field(..., min_length=1)
    corpo_despacho: str = Field(..., min_length=1)
    referencias_normativas: list[str] = Field(default_factory=list)
    justificativa_encaminhamento: str = Field(..., min_length=0)
    status_sugerido: str = Field(..., min_length=1)
    processo_numero: str | None = None
    numero_despacho: str = "___/CPPD/2026"


@router.get("/pdf-preview/{processo_id}")
async def pdf_preview(
    processo_id: UUID,
    corpo_editado: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Gera um PDF temporário do despacho para visualização no frontend sem exigir token (facilita abertura em nova aba)."""
    processo = await ProcessoService.get_processo(db=db, processo_id=str(processo_id))
    if not processo:
        raise HTTPException(status_code=404, detail="Processo não encontrado")

    # Usa o corpo editado enviado pelo front, ou o automático do banco, ou fallback
    corpo = corpo_editado or processo.despacho_automatico or "Despacho não gerado."

    usuario = getattr(processo, 'usuario', None)
    context = {
        "processo_numero": processo.numero,
        "setor_destino_sugerido": "CPPD / GABINETE", # Exemplo
        "assunto": f"Análise de {processo.tipo}",
        "professor_nome": getattr(usuario, 'nome', 'N/A'),
        "professor_setor": getattr(usuario, 'setor', 'N/A'),
        "professor_matricula": getattr(usuario, 'matricula', 'N/A') if hasattr(usuario, 'matricula') else 'N/A',
        "emitido_em": datetime.utcnow().strftime('%d/%m/%Y'),
        "corpo_despacho": corpo,
        "numero_despacho": "PREVIEW/2026"
    }

    try:
        html = templates.env.get_template("dispatch.html").render(context)
        from weasyprint import HTML
        template_dir = Path(__file__).resolve().parents[2] / "template"
        pdf_bytes = HTML(string=html, base_url=str(template_dir)).write_pdf()
        
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
    context.update(
        {
            "request": request,
            "processo_numero": payload.processo_numero or "",
        }
    )
    return templates.TemplateResponse(
        request=request,
        name="dispatch.html",
        context=context,
    )


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

    # Renderiza template para string
    context = payload.model_dump()
    usuario = getattr(processo, 'usuario', None)
    professor_nome = getattr(usuario, 'nome', '') if usuario else ''
    professor_setor = getattr(usuario, 'setor', '') if usuario else ''
    # matricula não está no modelo User por padrão; placeholder vazio
    professor_matricula = getattr(usuario, 'matricula', '') if usuario and hasattr(usuario, 'matricula') else ''

    context.update({
        "request": {},
        "processo_numero": payload.processo_numero or processo.numero,
        "professor_nome": professor_nome,
        "professor_setor": professor_setor,
        "professor_matricula": professor_matricula,
        "emitido_em": datetime.utcnow().strftime('%d/%m/%Y'),
    })
    try:
        html = templates.env.get_template("dispatch.html").render(context)
    except Exception as e:
        tb = traceback.format_exc()
        print("[DISPATCH SEND] Erro ao renderizar template:\n", tb, flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao renderizar template. Verifique os logs do servidor.",
        )

    # Tenta gerar PDF via WeasyPrint (import lazy) e salvar documento
    try:
        try:
            from weasyprint import HTML
            template_dir = Path(__file__).resolve().parents[2] / "template"
            pdf_bytes = HTML(string=html, base_url=str(template_dir)).write_pdf()
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
            arquivo_bytes = html.encode("utf-8")
            filename = f"despacho_{processo.numero}.html"
            documento = await ProcessoService.save_documento(
                db=db,
                processo_id=str(processo_id),
                tipo_doc="despacho_html",
                arquivo_bytes=arquivo_bytes,
                name_arquivo=filename,
            )
    except Exception as e:
        tb = traceback.format_exc()
        print("[DISPATCH SEND] Erro ao gerar/salvar despacho:\n", tb, flush=True)
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
