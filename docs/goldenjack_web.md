# Panel web GoldenJack

El panel se inicia con:

```powershell
analisis-caras\.venv\Scripts\python.exe src\access_control\webapp.py
```

Abrir `http://localhost:8080`, registrar el primer usuario y cargar los perfiles
en las listas **Prohibidos** y **Excluidos**. Las referencias, perfiles y alertas
se guardan localmente en `runtime/access_control/goldenjack.db`; ese directorio
no se versiona porque contiene datos sensibles.

La web llama a `FRIGATE_URL/api/config` para obtener las cámaras y a
`FRIGATE_URL/api/<camara>/latest.jpg` para mostrar la vista. El proceso
`sistema.py` escucha el tracking de Frigate, compara la cara contra los perfiles
prohibidos y registra una alerta con la captura para que aparezca en el panel.

Configurar en `.env` antes de exponerlo a una red:

```ini
FRIGATE_URL=http://127.0.0.1:5000
WEB_PORT=8080
WEB_SECRET_KEY=un_valor_aleatorio_largo
```

El flujo de recuperación crea un token de 30 minutos. Para entregar ese enlace
al correo real del operador falta conectar el proveedor SMTP o de correo que use
GoldenJack; el enlace se deja registrado en el log del servidor para desarrollo.
