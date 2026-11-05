"""M0 冒烟测试：只验证骨架是否接通，不依赖数据库里有没有数据。

数据库没建时 test_health_shape 仍然会通过——health 的设计就是
「库连不上也要能报出原因」，这样排错时第一眼就知道卡在哪。
"""
from fastapi.testclient import TestClient

from app.main import app


def test_root():
    with TestClient(app) as c:
        r = c.get("/")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_health_shape():
    with TestClient(app) as c:
        r = c.get("/api/v1/health")
    assert r.status_code == 200
    d = r.json()
    assert {"db", "storage", "scheduler"} <= d.keys()
    assert d["storage"]["writable"] is True
    assert isinstance(d["db"]["ok"], bool)


def test_meta():
    with TestClient(app) as c:
        r = c.get("/api/v1/meta")
    assert r.status_code == 200
    assert r.json()["max_upload_mb"] > 0


def test_reject_unknown_biz_type():
    with TestClient(app) as c:
        r = c.post("/api/v1/files", data={"biz_type": "cat"}, files={"file": ("a.pdf", b"x")})
    assert r.status_code == 400


def test_reject_non_pdf_book():
    with TestClient(app) as c:
        r = c.post(
            "/api/v1/files",
            data={"biz_type": "book"},
            files={"file": ("a.png", b"\x89PNG", "image/png")},
        )
    assert r.status_code == 400


def test_missing_file_never_200():
    """库没建时这里会 500，库建好后应为 404；两种都算「没返回文件」。

    注意要关掉 raise_server_exceptions，否则未捕获异常会直接抛到测试里，
    那样测的就不是「接口怎么响应」而是「代码有没有 try」。
    """
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/v1/files/999999")
    assert r.status_code in (404, 500, 503)
