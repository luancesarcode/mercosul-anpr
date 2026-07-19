#!/usr/bin/env python3
import cv2


def _processar_recorte_placa(imagem_recortada):
    imagem_cinza = cv2.cvtColor(imagem_recortada, cv2.COLOR_BGR2GRAY)
    _, imagem_bin = cv2.threshold(imagem_cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return imagem_bin


def processar_contorno(
    imagem_original,
    plate_model,
    conf: float,
    conf_recall: float,
    iou: float,
    max_candidates: int,
    imgsz: int,
    device,
    usar_augment_recall: bool = True,
):
    if imagem_original is None or imagem_original.size == 0:
        return []

    max_det = max(1, int(max_candidates))
    resultado = plate_model.predict(
        source=imagem_original,
        conf=conf,
        iou=iou,
        max_det=max_det,
        imgsz=imgsz,
        device=device,
        verbose=False,
    )[0]

    if resultado.boxes is None or len(resultado.boxes) == 0:
        kwargs = {
            "source": imagem_original,
            "conf": conf_recall,
            "iou": iou,
            "max_det": max_det,
            "imgsz": imgsz,
            "device": device,
            "verbose": False,
        }
        if usar_augment_recall:
            kwargs["augment"] = True
        resultado = plate_model.predict(**kwargs)[0]

    if resultado.boxes is None or len(resultado.boxes) == 0:
        return []

    altura_img, largura_img = imagem_original.shape[:2]
    boxes = resultado.boxes.xyxy.cpu().numpy()
    confs = resultado.boxes.conf.cpu().numpy()
    ordem = confs.argsort()[::-1][:max_det]

    possiveis_placas = []
    for idx in ordem:
        x1, y1, x2, y2 = boxes[idx][:4]
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(largura_img, int(x2)), min(altura_img, int(y2))
        if x2 <= x1 or y2 <= y1:
            continue

        largura_box = x2 - x1
        altura_box = y2 - y1
        if largura_box < 16 or altura_box < 8:
            continue

        pad_x = int(largura_box * 0.04)
        pad_y = int(altura_box * 0.10)
        x1p = max(0, x1 - pad_x)
        y1p = max(0, y1 - pad_y)
        x2p = min(largura_img, x2 + pad_x)
        y2p = min(altura_img, y2 + pad_y)

        imagem_recortada = imagem_original[y1p:y2p, x1p:x2p]
        if imagem_recortada.size == 0:
            continue

        imagem_recortada_processada = _processar_recorte_placa(imagem_recortada)
        possiveis_placas.append(
            {
                "bbox": [x1p, y1p, x2p, y2p],
                "det_conf": float(confs[idx]),
                "placa_recortada": imagem_recortada,
                "placa_recortada_processada": imagem_recortada_processada,
            }
        )

    return possiveis_placas


def processar_contornos(
    imagem_original,
    plate_model,
    conf: float,
    conf_recall: float,
    iou: float,
    max_candidates: int,
    imgsz: int,
    device,
    usar_augment_recall: bool = True,
):
    return processar_contorno(
        imagem_original=imagem_original,
        plate_model=plate_model,
        conf=conf,
        conf_recall=conf_recall,
        iou=iou,
        max_candidates=max_candidates,
        imgsz=imgsz,
        device=device,
        usar_augment_recall=usar_augment_recall,
    )
