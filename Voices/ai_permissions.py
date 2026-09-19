def is_authenticated_user(user, **kwargs):
    return bool(user and getattr(user, "is_authenticated", False))
