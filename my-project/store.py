from typing import Any, Dict

from luna_service import load_user_brain, save_user_brain, load_core_brain, is_admin


def get_user_state(user_id: str) -> Dict[str, Any]:
    state = load_user_brain(user_id)
    if is_admin(user_id):
        core = load_core_brain()
        state["trained_knowledge"] = core.get("trained_knowledge", [])
        state["admin_mode"] = True
    return state


def save_user_state(user_id: str, state: Dict[str, Any]) -> None:
    save_user_brain(user_id, state)
