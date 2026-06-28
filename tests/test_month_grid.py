from __future__ import annotations

from jimini.hostigamiento.comandos import _month_grid


def test_enero_sin_tareas():
    grid = _month_grid(2026, 1, {})
    cells = "\n".join(grid.split("\n")[:-1])
    assert "🗓️" in cells
    assert "Lun" in cells
    assert "1" in grid or " 1" in grid
    assert "31" in grid
    assert "🔵" not in cells
    assert "⚡" not in cells


def test_julio_con_tarea_laboral():
    tareas = {"2026-07-05": [{"ambito": "laboral", "id": "t1"}]}
    grid = _month_grid(2026, 7, tareas)
    cells = "\n".join(grid.split("\n")[:-1])
    assert "🔵" in cells
    assert "⚡" not in cells


def test_febrero_no_bisiesto():
    grid = _month_grid(2025, 2, {})
    assert "28" in grid
    assert "29" not in grid


def test_mes_con_tareas_vencidas_y_no():
    tareas = {
        "2026-07-03": [{"ambito": "laboral", "id": "t1", "fecha_vence": "2026-07-03"}],
        "2026-07-15": [{"ambito": "personal", "id": "t2", "fecha_vence": "2026-07-15"}],
    }
    grid = _month_grid(2026, 7, tareas)
    assert "🔵" in grid
    assert "🟠" in grid
