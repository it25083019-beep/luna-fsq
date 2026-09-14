from typing import Any, Dict

from luna_service import load_user_brain, save_user_brain, is_admin


def get_user_state(user_id: str) -> Dict[str, Any]:
    from privacy_vault import public_client_state

    state = load_user_brain(user_id)
    view = public_client_state(state)
    if is_admin(user_id):
        view["admin_mode"] = True
    return view


def save_user_state(user_id: str, state: Dict[str, Any]) -> None:
    save_user_brain(user_id, state)
