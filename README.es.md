# Magicou Recognizer

**Motor independiente para reconocer cartas físicas de Magic: The Gathering.**

[English documentation](README.md) · [API](docs/api.md) · [Arquitectura](docs/architecture.md)

Usalo como biblioteca Python, herramienta de consola o servicio HTTP. Combina DINOv2, pHash y verificación geométrica, con OCR opcional para confirmar la impresión. Scryfall aporta el catálogo y los precios de referencia.

## Empezar

Necesitás Python 3.11 o superior y un entorno virtual activado.

```sh
git clone https://github.com/GonnRuiz/magicou-recognizer.git
cd magicou-recognizer
python -m venv .venv
```

En PowerShell: `.venv\Scripts\Activate.ps1`. En Linux/macOS: `source .venv/bin/activate`.

```sh
python -m pip install -e .
magicou-recognizer model
magicou-recognizer sync
magicou-recognizer build --limit 100
magicou-recognizer coverage
magicou-recognizer identify carta.jpg --cropped
magicou-recognizer serve
```

El API queda en `http://127.0.0.1:8015`; su documentación interactiva, en `/docs`. Para una foto con fondo, omití `--cropped`.

Para construir el índice completo del catálogo importado:

```sh
magicou-recognizer build --workers 4
```

La primera construcción puede tardar horas y ocupar varios GB. El catálogo y las imágenes realmente indexadas se cuentan por separado. El dataset por defecto contiene impresiones en inglés o el idioma disponible cuando no existe versión inglesa; `sync --all-languages` importa otros registros y requiere construir su índice.

## Integración en Python

```python
import numpy as np
from PIL import Image, ImageOps
from magicou_recognizer import Recognizer

motor = Recognizer("./data")
with Image.open("foto.jpg") as imagen:
    rgb = np.asarray(ImageOps.exif_transpose(imagen).convert("RGB"))
resultado = motor.identify(rgb)
print(resultado["status"], resultado["candidates"])
```

También podés consumir `POST /identify` desde tu backend y consultar `GET /cards/{uuid}/price?finish=foil` después de elegir una impresión. Los acabados admitidos son `nonfoil`, `foil` y `etched`.

La inferencia usa CPU local y no requiere una API de IA paga. Los precios y las referencias que no estén cacheadas requieren Internet. Las interfaces de cámara, cuentas y colecciones pertenecen a la aplicación que integre el motor.

## Modelo de IA y conexiones

El modelo es **DINOv2-small en formato ONNX**, ejecutado en CPU mediante ONNX Runtime. `magicou-recognizer model` descarga una revisión fija y verifica su SHA-256. Son pesos genéricos de visión; el índice de referencias permite buscar las cartas de Magic sin entrenar un clasificador nuevo.

Las fotos se procesan en el proceso Python que ejecutes. Si integrás el API HTTP, se envían al servidor que configures. Las descargas del modelo, actualizaciones del catálogo, imágenes de referencia no cacheadas y consultas de precios usan Internet. Cada integrador aporta su configuración y credenciales; los datos generados quedan fuera de Git.

## Alcance

El snapshot de referencia del 25 de noviembre de 2026 incluye 115.084 caras del catálogo físico seleccionado. Tres fotos reales pasaron la prueba contra esa galería; esa muestra no demuestra precisión universal. Edición, idioma, acabado, reflejos y diseños especiales necesitan validación adicional. Un precio desconocido sigue siendo desconocido.

Código MIT. Se conservan las atribuciones de los componentes reutilizados; los pesos y el material de las cartas tienen condiciones independientes. Ver [licencias](THIRD_PARTY_NOTICES.md) y la [guía completa](README.md).
