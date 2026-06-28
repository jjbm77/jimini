from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from jimini.hostigamiento.core import (
    auto_limpiar_modos,
    debe_alertar,
    dentro_horario_activo,
    frecuencia_nivel,
)


class TestCalcularNivel:
    @patch("jimini.hostigamiento.core.get_db")
    def test_nivel_aviso(self, mock_db):
        mock = MagicMock()
        mock.rpc.return_value.execute.return_value.data = [0]
        mock_db.return_value = mock

        from jimini.hostigamiento.core import calcular_nivel
        assert calcular_nivel("2026-07-05", datetime(2026, 7, 4, tzinfo=UTC)) == 0

    @patch("jimini.hostigamiento.core.get_db")
    def test_nivel_vence_hoy(self, mock_db):
        mock = MagicMock()
        mock.rpc.return_value.execute.return_value.data = [1]
        mock_db.return_value = mock

        from jimini.hostigamiento.core import calcular_nivel
        assert calcular_nivel("2026-07-05", datetime(2026, 7, 5, tzinfo=UTC)) == 1

    @patch("jimini.hostigamiento.core.get_db")
    def test_nivel_vencida_corto(self, mock_db):
        mock = MagicMock()
        mock.rpc.return_value.execute.return_value.data = [2]
        mock_db.return_value = mock

        from jimini.hostigamiento.core import calcular_nivel
        assert calcular_nivel("2026-07-05", datetime(2026, 7, 6, tzinfo=UTC)) == 2

    @patch("jimini.hostigamiento.core.get_db")
    def test_nivel_vencida_largo(self, mock_db):
        mock = MagicMock()
        mock.rpc.return_value.execute.return_value.data = [4]
        mock_db.return_value = mock

        from jimini.hostigamiento.core import calcular_nivel
        assert calcular_nivel("2026-07-05", datetime(2026, 7, 15, tzinfo=UTC)) == 4

    @patch("jimini.hostigamiento.core.get_db")
    def test_nivel_sin_fecha(self, mock_db):
        from jimini.hostigamiento.core import calcular_nivel
        assert calcular_nivel(None) == -1


class TestFrecuencia:
    def test_frecuencia_nivel_0(self):
        assert frecuencia_nivel(0) is None

    def test_frecuencia_nivel_1(self):
        from datetime import timedelta
        assert frecuencia_nivel(1) == timedelta(hours=4)

    def test_frecuencia_nivel_4(self):
        from datetime import timedelta
        assert frecuencia_nivel(4) == timedelta(days=1)


class TestDebeAlertar:
    def test_sin_modo(self):
        assert debe_alertar("laboral", 2, None, None) is True
        assert debe_alertar("personal", 1, None, None) is True

    def test_vacaciones_laboral_silenciado(self):
        modo = {"activo": True, "fecha_liberacion": "2026-08-01"}
        assert debe_alertar("laboral", 3, modo, None) is False

    def test_vacaciones_personal_nivel_bajo_silenciado(self):
        modo = {"activo": True, "fecha_liberacion": "2026-08-01"}
        assert debe_alertar("personal", 1, modo, None) is False

    def test_vacaciones_personal_nivel_alto_sigue(self):
        modo = {"activo": True, "fecha_liberacion": "2026-08-01"}
        assert debe_alertar("personal", 3, modo, None) is True


class TestHorarioActivo:
    @patch("jimini.hostigamiento.core.datetime")
    def test_dentro_horario(self, mock_datetime):
        mock_datetime.now.return_value.hour = 14
        assert dentro_horario_activo("America/Lima") is True

    @patch("jimini.hostigamiento.core.datetime")
    def test_fuera_horario(self, mock_datetime):
        mock_datetime.now.return_value.hour = 22
        assert dentro_horario_activo("America/Lima") is False


class TestAutoLimpiar:
    @patch("jimini.hostigamiento.core.get_modo")
    @patch("jimini.hostigamiento.core.get_db")
    def test_limpia_modo_expirado(self, mock_db, mock_get_modo):
        mock_get_modo.return_value = {"activo": True, "fecha_liberacion": "2026-01-01T00:00:00"}
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst

        auto_limpiar_modos()

        mock_db_inst.table.return_value.update.assert_called()
