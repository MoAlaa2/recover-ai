"""Consultant asks the which-item question once, on the photo turn only."""
import inspect

from app.services import consultant as C


def test_which_item_nudge_only_on_photo_turn():
    src = inspect.getsource(C._chat)
    assert ('available and not session.get("chosen_targets") and image_path'
            in src)


def test_prompt_says_once_never_repeat():
    assert "Never repeat that question on later turns" in C.SYSTEM_PROMPT
