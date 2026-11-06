"""M1 的四条安全底线。

登录成功、密码错、未登录被挡、越权被挡——前两条验证功能，
后两条才是真正要守住的东西：任何一条退化都意味着数据能被别人读到。
"""
from tests.conftest import PASSWORD


def test_login_ok(account_factory, client):
    info = account_factory()
    r = client.post(
        "/api/v1/auth/login",
        json={"username": info["username"], "password": PASSWORD},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["account"]["username"] == info["username"]
    assert [c["id"] for c in body["children"]] == [info["child_id"]]
    # Cookie 必须是 HttpOnly：JS 读不到，XSS 也拿不走
    set_cookie = r.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "st_session=" in set_cookie


def test_login_wrong_password(account_factory, client):
    info = account_factory()
    r = client.post(
        "/api/v1/auth/login",
        json={"username": info["username"], "password": "not-the-password"},
    )
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "pytest_no_such_user", "password": PASSWORD},
    )
    assert r.status_code == 401
    # 与密码错误的提示完全一致，避免被用来探测用户名
    assert r.json()["detail"] == "登录名或密码不正确"


def test_me_requires_login(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/children").status_code == 401


def test_children_isolated_between_accounts(account_factory, client):
    """A 登录后碰不到 B 的孩子：这是 child_id 从参数改为上下文推导的意义。"""
    a = account_factory(child_name="A 家娃")
    b = account_factory(child_name="B 家娃")

    assert client.post(
        "/api/v1/auth/login", json={"username": a["username"], "password": PASSWORD}
    ).status_code == 200

    # 自己的能读
    assert client.get(f"/api/v1/children/{a['child_id']}").status_code == 200
    # 别人的读不到
    assert client.get(f"/api/v1/children/{b['child_id']}").status_code == 403
    # 不存在的走 404，与 403 区分开
    assert client.get("/api/v1/children/99999999").status_code == 404
    # 列表里也不会出现别人家的孩子
    ids = [c["id"] for c in client.get("/api/v1/children").json()]
    assert b["child_id"] not in ids


def test_patch_child_updates_only_given_fields(auth_client):
    client, info = auth_client
    cid = info["child_id"]

    r = client.patch(f"/api/v1/children/{cid}", json={"grade": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["grade"] == 5
    assert body["name"] == "测试娃"      # 没传的字段保持原值
    assert body["edition"] == "人教版"

    assert client.patch(f"/api/v1/children/{cid}", json={"grade": 7}).status_code == 422
    assert client.patch(f"/api/v1/children/{cid}", json={"name": ""}).status_code == 422


def test_upload_requires_login(client, auth_client):
    """匿名上传必须被挡在落盘之前。"""
    r = client.post(
        "/api/v1/files",
        data={"biz_type": "book"},
        files={"file": ("a.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    assert r.status_code == 401


def test_upload_validates_biz_type_when_logged_in(auth_client):
    client, _ = auth_client
    r = client.post(
        "/api/v1/files",
        data={"biz_type": "cat"},
        files={"file": ("a.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    assert r.status_code == 400


def test_upload_book_must_be_pdf(auth_client):
    client, _ = auth_client
    r = client.post(
        "/api/v1/files",
        data={"biz_type": "book"},
        files={"file": ("a.png", b"\x89PNG", "image/png")},
    )
    assert r.status_code == 400
