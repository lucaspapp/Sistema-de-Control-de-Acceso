# Componentes retirados de producción

Estos scripts se conservan como referencia y ya no se inician con
`scripts/start_windows.bat`:

- `sistema.py`: conteo de entradas/salidas, estadísticas, Excel y edad/género.
- `trackeo.py`: lógica de zonas de entrada y salida.
- `detect.py`: servicio de edad y género.
- `dashboard.py`: dashboard de escritorio de estadísticas.

Producción usa `src/access_control/sistema.py`: solo monitorea rostros
prohibidos mientras Frigate mantiene activo cada tracking de persona.
