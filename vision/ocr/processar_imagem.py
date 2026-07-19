#!/usr/bin/env python3
import cv2


def processar_imagem(imagem_placa):
    imagem_cinza = cv2.cvtColor(imagem_placa, cv2.COLOR_BGR2GRAY)
    imagem_cinza = cv2.bilateralFilter(imagem_cinza, 9, 75, 75)
    imagem_limiarizada = cv2.adaptiveThreshold(
        imagem_cinza,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )
    return imagem_limiarizada
