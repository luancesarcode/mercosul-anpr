from .aplicar_ocr import aplicar_ocr
from .processar_contorno import processar_contorno, processar_contornos
from .processar_imagem import processar_imagem
from .utils import PADDLE_LANGS, carregar_paddle

__all__ = [
    "aplicar_ocr",
    "processar_contorno",
    "processar_contornos",
    "processar_imagem",
    "PADDLE_LANGS",
    "carregar_paddle",
]
