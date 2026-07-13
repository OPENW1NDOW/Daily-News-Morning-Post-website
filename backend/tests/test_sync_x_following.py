def test_sync_preserves_enabled_and_marks_unfollowed(db, monkeypatch):
    from app.models import XAccount
    from app.pipeline import sync_x_following as mod

    db.add(XAccount(x_user_id="1", handle="keep", display_name="K", enabled=False, is_following=True))
    db.add(XAccount(x_user_id="2", handle="gone", display_name="G", enabled=True, is_following=True))
    db.commit()

    monkeypatch.setattr(mod, "list_following", lambda: [
        {"x_user_id": "1", "handle": "keep", "display_name": "Keep2", "avatar_url": None},
        {"x_user_id": "3", "handle": "new", "display_name": "New", "avatar_url": None},
    ])
    mod.sync_following_accounts(db)
    db.commit()

    a1 = db.query(XAccount).filter_by(x_user_id="1").one()
    assert a1.enabled is False  # 不覆盖
    assert a1.is_following is True
    assert a1.display_name == "Keep2"
    a2 = db.query(XAccount).filter_by(x_user_id="2").one()
    assert a2.is_following is False
    a3 = db.query(XAccount).filter_by(x_user_id="3").one()
    assert a3.enabled is True


def test_sync_failure_does_not_flip_flags(db, monkeypatch):
    from app.models import XAccount
    from app.pipeline import sync_x_following as mod

    db.add(XAccount(x_user_id="1", handle="a", display_name="A", enabled=True, is_following=True))
    db.commit()

    def boom():
        raise RuntimeError("bird down")

    monkeypatch.setattr(mod, "list_following", boom)
    import pytest
    with pytest.raises(RuntimeError):
        mod.sync_following_accounts(db)
    assert db.query(XAccount).filter_by(x_user_id="1").one().is_following is True
