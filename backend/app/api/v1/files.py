"""文件上传与读取。

设计要点（技术方案 v1.1 缺口 1）：
- 文件落磁盘，库里只存 rel_path，绝不进 BLOB、不用 base64。
- 上传边读边写，40MB 教材不进内存。
- 读取走 FileResponse，支持 Range 与浏览器缓存。

M1 起两个接口都要求登录，并且 child_id 由服务端从当前账号推导，
不再信任前端传入——M0 时那是个人人可越权的洞。
"""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import default_child, get_current_account, owned_child
from app.core.config import settings
from app.core.db import get_db
from app.integrations.storage import get_storage
from app.models import Account, FileObject

router = APIRouter(tags=["文件"])

ALLOWED_BIZ = {"book", "shot", "avatar", "mistake"}
MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@router.post("/files", summary="上传文件，返回 file_id")
def upload_file(
    biz_type: str = Form(..., description="book / shot / avatar / mistake"),
    file: UploadFile = File(...),
    child_id: int | None = Form(None, description="不传则落到默认孩子；传了必须属于本账号"),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if biz_type not in ALLOWED_BIZ:
        raise HTTPException(400, f"biz_type 只能是 {sorted(ALLOWED_BIZ)}")

    # 归属校验放在落盘之前：越权请求不该在磁盘上留下任何文件
    child = (
        owned_child(child_id, account, db) if child_id is not None
        else default_child(account, db)
    )

    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    if file.size and file.size > limit:
        raise HTTPException(413, f"文件超过 {settings.MAX_UPLOAD_MB} MB 上限")

    orig_name = Path(file.filename or "unnamed").name
    suffix = Path(orig_name).suffix.lower()
    if biz_type == "book" and suffix != ".pdf":
        raise HTTPException(400, "教材只接受 PDF")
    if biz_type != "book" and suffix not in MIME_BY_SUFFIX:
        raise HTTPException(400, "照片只接受 jpg / png / webp")

    storage = get_storage()
    rel_path, size, sha256 = storage.save(file.file, biz_type, orig_name)

    # 落盘后才拿得到真实大小，超限要回收，避免留下孤儿文件
    if size > limit:
        storage.delete(rel_path)
        raise HTTPException(413, f"文件超过 {settings.MAX_UPLOAD_MB} MB 上限")

    obj = FileObject(
        child_id=child.id,
        biz_type=biz_type,
        rel_path=rel_path,
        orig_name=orig_name,
        mime=MIME_BY_SUFFIX.get(suffix, "application/octet-stream"),
        size_bytes=size,
        sha256=sha256,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    return {
        "id": obj.id,
        "biz_type": obj.biz_type,
        "url": f"/api/v1/files/{obj.id}",
        "size_bytes": size,
        "orig_name": orig_name,
    }


@router.get("/files/{file_id}", summary="读取文件，支持 Range")
def read_file(
    file_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    obj = db.get(FileObject, file_id)
    if not obj:
        raise HTTPException(404, "文件不存在")
    # 图片和 PDF 由 <img>/<iframe> 直接请求，浏览器会自动带上 Cookie，
    # 所以这里能校验归属；换成 Authorization 头就做不到，见技术方案缺口 1。
    if obj.child_id is not None:
        owned_child(obj.child_id, account, db)

    try:
        p = get_storage().path(obj.rel_path)
    except PermissionError:
        raise HTTPException(403, "路径越界")
    if not p.is_file():
        raise HTTPException(410, "文件已丢失，可能是目录被移动或清理过")

    return FileResponse(
        p,
        media_type=obj.mime,
        filename=obj.orig_name or None,
        headers={"Cache-Control": "private, max-age=86400"},
    )
