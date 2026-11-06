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


def test_upload_rejects_anonymous():
    """M1 起上传要求登录。

    参数校验与鉴权谁先返回都可以接受，但**不能是 2xx**——匿名请求
    绝不能写入 file_object 或在磁盘上留下文件。带登录态的校验见
    tests/test_auth.py::test_upload_validates_biz_type_when_logged_in。
    """
    with TestClient(app) as c:
        r = c.post("/api/v1/files", data={"biz_type": "cat"}, files={"file": ("a.pdf", b"x")})
    assert r.status_code in (400, 401)


def test_read_file_rejects_anonymous():
    with TestClient(app) as c:
        r = c.get("/api/v1/files/1")
    assert r.status_code == 401


def test_missing_file_never_200():
    """匿名请求应停在 401；登录后不存在的 id 才是 404。

    注意要关掉 raise_server_exceptions，否则未捕获异常会直接抛到测试里，
    那样测的就不是「接口怎么响应」而是「代码有没有 try」。
    """
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/v1/files/999999")
    assert r.status_code in (401, 404, 500, 503)
