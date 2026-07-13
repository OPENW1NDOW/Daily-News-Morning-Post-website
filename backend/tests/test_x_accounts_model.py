from app.models import XAccount


def test_x_account_unique_user_id(db):
    db.add(XAccount(x_user_id="1", handle="a", display_name="A", enabled=True, is_following=True))
    db.commit()
    db.add(XAccount(x_user_id="1", handle="b", display_name="B", enabled=True, is_following=True))
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.commit()
