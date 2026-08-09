---
applyTo: "backend/tests/**/*.py"
---

# 後端測試規範（自動注入）

本指引在編輯 `backend/tests/` 下任何測試檔案時自動生效。

## 測試框架

- pytest + pytest-asyncio（async 測試）
- httpx.AsyncClient（FastAPI TestClient 替代）
- unittest.mock / pytest-mock（Mock 策略）

## 檔案命名

| 類型 | 規則 | 範例 |
|------|------|------|
| 測試檔 | `test_<module>_<layer>.py` | `test_weighing_router.py` |
| Fixture | 集中在 `conftest.py` | `conftest.py` |
| Factory | `factories/<module>.py` | `factories/weighing.py` |

## 測試結構（AAA 模式）

```python
@pytest.mark.asyncio
async def test_create_weighing_record_success(client, db_session):
    # Arrange — 準備測試資料
    payload = {"vehicle_no": "粵A12345", "material_code": "M001"}

    # Act — 執行待測行為
    response = await client.post("/api/v1/weighing-records", json=payload)

    # Assert — 驗證結果
    assert response.status_code == 201
    data = response.json()
    assert data["data"]["vehicle_no"] == "粵A12345"
```

## Fixture 規範

- `conftest.py` 提供：`db_session`、`client`、`auth_headers`、`sample_user`
- 共用 fixture 使用 `@pytest.fixture(scope="session")` 或 `scope="function"`
- DB fixture 必須在測試後 rollback（使用 `SAVEPOINT` 策略）

## Mock 策略

| 場景 | Mock 方式 |
|------|----------|
| 外部 API 呼叫 | `respx` 或 `unittest.mock.patch` |
| 設備驅動（IC卡/地磅） | 使用 `poc/` 下的 Mock class |
| 資料庫 | 使用真實 test DB，不 Mock ORM |
| 時間 | `freezegun` 或 `unittest.mock.patch('datetime')` |

## 測試分類標記

```python
@pytest.mark.unit        # 單元測試（無 DB/網路）
@pytest.mark.integration # 整合測試（需 DB）
@pytest.mark.e2e         # 端對端測試
@pytest.mark.slow        # 慢速測試（>5s）
```

## 必覆蓋場景

每個 API endpoint 至少覆蓋：
1. ✅ 正常建立/查詢/更新/刪除
2. ✅ 必填欄位缺失 → 422
3. ✅ 不存在的 ID → 404
4. ✅ 未授權存取 → 401
5. ✅ 權限不足 → 403（若有角色控制）
