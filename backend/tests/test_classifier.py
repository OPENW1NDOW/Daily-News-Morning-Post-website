"""
分类器冒烟测试：mock llm 公共层客户端，验证解析逻辑、边界情况、容错。
classifier 已改用 app.pipeline.llm.chat_json，测试统一 patch llm.get_client。
"""
import json
import threading
from unittest.mock import MagicMock, patch


def _mock_client(content: str) -> MagicMock:
    """构造返回固定 content 的 mock OpenAI 客户端。"""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    return mock_client


# ---------- _classify_batch ----------

class TestClassifyBatch:
    def test_parses_list_response(self):
        """API 直接返回数组。"""
        payload = json.dumps([
            {"id": 1, "category": "ai", "importance": 85, "keep": True},
            {"id": 2, "category": "tech", "importance": 60, "keep": True},
        ])

        with patch("app.pipeline.llm.get_client", return_value=_mock_client(payload)):
            from app.pipeline.classifier import _classify_batch
            results = _classify_batch([
                {"id": 1, "title": "GPT-5", "summary": "OpenAI 发布 GPT-5"},
                {"id": 2, "title": "Vision Pro", "summary": "苹果新头显"},
            ])

        assert len(results) == 2
        assert results[0]["category"] == "ai"
        assert results[0]["importance"] == 85
        assert results[1]["category"] == "tech"

    def test_parses_dict_wrapped_list(self):
        """部分模型 json_object 模式可能把数组包在 key 下。"""
        payload = json.dumps({"results": [
            {"id": 5, "category": "internet", "importance": 90, "keep": True},
        ]})

        with patch("app.pipeline.llm.get_client", return_value=_mock_client(payload)):
            from app.pipeline.classifier import _classify_batch
            results = _classify_batch([
                {"id": 5, "title": "平台新规", "summary": "某平台调整规则"},
            ])

        assert len(results) == 1
        assert results[0]["category"] == "internet"

    def test_marks_keep_false_as_other(self):
        """keep=false 的条目标记为 other。"""
        payload = json.dumps([
            {"id": 1, "category": "ai", "importance": 30, "keep": False},
            {"id": 2, "category": "tech", "importance": 70, "keep": True},
        ])

        with patch("app.pipeline.llm.get_client", return_value=_mock_client(payload)):
            from app.pipeline.classifier import _classify_batch
            results = _classify_batch([
                {"id": 1, "title": "广告软文", "summary": "某产品促销"},
                {"id": 2, "title": "真正新闻", "summary": "Apple 发布新品"},
            ])

        assert results[0]["keep"] is False
        assert results[1]["keep"] is True

    def test_api_error_returns_empty(self):
        """API 异常时返回空列表，不抛异常（llm 层对非限流异常不重试）。"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API 超时")

        with patch("app.pipeline.llm.get_client", return_value=mock_client):
            from app.pipeline.classifier import _classify_batch
            results = _classify_batch([
                {"id": 1, "title": "Test", "summary": "Test"},
            ])

        assert results == []

    def test_malformed_json_returns_empty(self):
        """API 返回非 JSON 时返回空列表。"""
        with patch("app.pipeline.llm.get_client", return_value=_mock_client("这不是 JSON")):
            from app.pipeline.classifier import _classify_batch
            results = _classify_batch([{"id": 1, "title": "T", "summary": "S"}])

        assert results == []

    def test_empty_items_returns_empty(self):
        """空列表直接返回空。"""
        with patch("app.pipeline.llm.get_client", return_value=_mock_client("[]")):
            from app.pipeline.classifier import _classify_batch
            results = _classify_batch([])

        assert results == []


# ---------- classify_articles ----------

class TestClassifyArticles:
    def _fake_article(self, **kw):
        art = MagicMock()
        art.id = kw.get("id", 1)
        art.title = kw.get("title", "Test")
        art.raw_summary = kw.get("raw_summary", "Summary")
        art.category = None
        art.importance = None
        return art

    def test_classifies_and_updates_fields(self):
        """正常分类流程：更新 category 和 importance，返回 (成功条数, 失败批次数)。"""
        articles = [self._fake_article(id=1), self._fake_article(id=2)]

        payload = json.dumps([
            {"id": 1, "category": "ai", "importance": 80, "keep": True},
            {"id": 2, "category": "tech", "importance": 55, "keep": True},
        ])

        db = MagicMock()
        with patch("app.pipeline.llm.get_client", return_value=_mock_client(payload)):
            from app.pipeline.classifier import classify_articles
            count, failed_batches = classify_articles(db, articles)

        assert count == 2
        assert failed_batches == 0
        assert articles[0].category == "ai"
        assert articles[0].importance == 80
        assert articles[1].category == "tech"
        assert articles[1].importance == 55

    def test_keep_false_becomes_other(self):
        """keep=false 归类为 other。"""
        articles = [self._fake_article(id=1)]

        payload = json.dumps([
            {"id": 1, "category": "ai", "importance": 20, "keep": False},
        ])

        db = MagicMock()
        with patch("app.pipeline.llm.get_client", return_value=_mock_client(payload)):
            from app.pipeline.classifier import classify_articles
            classify_articles(db, articles)

        assert articles[0].category == "other"

    def test_unknown_category_becomes_other(self):
        """不在 CATEGORIES 中的 category 标记为 other。"""
        articles = [self._fake_article(id=1)]

        payload = json.dumps([
            {"id": 1, "category": "sports", "importance": 50, "keep": True},
        ])

        db = MagicMock()
        with patch("app.pipeline.llm.get_client", return_value=_mock_client(payload)):
            from app.pipeline.classifier import classify_articles
            classify_articles(db, articles)

        assert articles[0].category == "other"

    def test_invalid_importance_clamped_to_50(self):
        """importance 不合法时使用默认值 50。"""
        articles = [self._fake_article(id=1)]

        payload = json.dumps([
            {"id": 1, "category": "ai", "importance": "high", "keep": True},
        ])

        db = MagicMock()
        with patch("app.pipeline.llm.get_client", return_value=_mock_client(payload)):
            from app.pipeline.classifier import classify_articles
            classify_articles(db, articles)

        assert articles[0].importance == 50

    def test_batch_failure_skips_gracefully(self):
        """一批分类失败时跳过并计入失败批次，不阻塞后续批次。"""
        articles = [self._fake_article(id=i) for i in range(120)]  # 两批（_BATCH_SIZE=60）
        lock = threading.Lock()
        call_ids: list[set] = []

        # 批次并发执行，按 payload 内容判定失败批（含 id 0 的第一批），保证确定性
        def side_effect(**kwargs):
            items = json.loads(kwargs["messages"][1]["content"])
            with lock:
                call_ids.append({item["id"] for item in items})
            if any(item["id"] == 0 for item in items):
                raise Exception("网络错误")
            result = [
                {"id": item["id"], "category": "ai", "importance": 60, "keep": True}
                for item in items
            ]
            mock = MagicMock()
            mock.choices = [MagicMock(message=MagicMock(content=json.dumps(result)))]
            return mock

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = side_effect

        db = MagicMock()
        with patch("app.pipeline.llm.get_client", return_value=mock_client):
            from app.pipeline.classifier import classify_articles
            count, failed_batches = classify_articles(db, articles)

        # 只有第二批（60 条）成功，第一批计入失败批次
        assert count == 60
        assert failed_batches == 1
        assert len(call_ids) == 2
