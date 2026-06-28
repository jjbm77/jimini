from __future__ import annotations

from jimini.hostigamiento.worker import _build_keyboard


def test_nivel_0():
    kb = _build_keyboard("t1", 0)
    assert kb == [[{"text": "✅ Completar", "callback_data": "completar:t1"}]]


def test_nivel_1():
    kb = _build_keyboard("t1", 1)
    assert kb == [
        [
            {"text": "⏳ 2h", "callback_data": "snooze_2h:t1"},
            {"text": "📅 Mañana", "callback_data": "snooze_manana:t1"},
        ],
        [{"text": "✅ Completar", "callback_data": "completar:t1"}],
    ]


def test_nivel_2():
    kb = _build_keyboard("t1", 2)
    assert kb == [
        [
            {"text": "⏳ 2h", "callback_data": "snooze_2h:t1"},
            {"text": "📅 Mañana", "callback_data": "snooze_manana:t1"},
        ],
        [{"text": "✅ Completar", "callback_data": "completar:t1"}],
    ]


def test_nivel_3():
    kb = _build_keyboard("t1", 3)
    assert kb == [
        [{"text": "✅ Completar", "callback_data": "completar:t1"}],
        [{"text": "🗑️ Descartar", "callback_data": "descartar:t1"}],
    ]


def test_nivel_4():
    kb = _build_keyboard("t1", 4)
    assert kb == [
        [{"text": "✅ Completar", "callback_data": "completar:t1"}],
        [{"text": "🗑️ Descartar", "callback_data": "descartar:t1"}],
    ]


def test_nivel_default():
    kb = _build_keyboard("t1", 99)
    assert kb == [[{"text": "✅ Completar", "callback_data": "completar:t1"}]]
