from .aplicar_ocr import aplicar_ocr
from .processar_imagem import gerar_variantes_ocr
from .utils import PADDLE_LANGS, carregar_paddle

__all__ = [
    "aplicar_ocr",
    "gerar_variantes_ocr",
    "PADDLE_LANGS",
    "carregar_paddle",
]
