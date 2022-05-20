from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import colorgram
import numpy as np
from PIL import Image
from skimage import color as spaces

from spy_collage.color_problem import ColorMatrix, ColorSpace, KeyObject, solve_colors


@dataclass
class ImageFeatures:
    features: np.ndarray
    image_path: Path
    __image: Optional[Image.Image]

    @property
    def image(self):
        if self.__image is None:
            self.__image = Image.open(self.image_path)
        return self.__image

    def to_dict(self):
        return {"features": list(self.features), "image_path": str(self.image_path)}

    @staticmethod
    def from_dict(d: dict):
        return ImageFeatures(np.asarray(d["features"]), Path(d["image_path"]), None)


def get_features(image_path) -> ImageFeatures:
    colors: list[colorgram.Color] = colorgram.extract(image_path, 1)
    features = []
    for c in colors:
        rgb = list(c.rgb)
        lab = spaces.rgb2lab(rgb)
        features.extend(lab)
    return ImageFeatures(np.asarray(features), image_path, None)


def lap_collage(
    features: list[ImageFeatures], shape: tuple[int, int], key_objects: list[KeyObject]
):
    width, height = shape
    color_matrix = ColorMatrix(np.asarray([f.features for f in features]), ColorSpace.CIELAB)

    # key_points = [
    #     KeyPoint(0, 0, np.array([255, 0, 0])),
    #     KeyPoint(int(1 * width), int(1 * height), np.array([255, 0, 255])),
    #     KeyPoint(int(0.5 * width), int(0.5 * height), np.array([0, 255, 0])),
    # ]
    # key_points = [
    #     KeyLine(
    #         int(0.5 * width),
    #         int(0.25 * height),
    #         int(0.55 * width),
    #         int(0.75 * height),
    #         np.array([255, 0, 255]),
    #     )
    # ]
    # key_points = [KeyPoint(int(0.5 * width), int(0.5 * height), np.array([255, 255, 255]))]
    # key_points = [
    #     mkpoint(0, 0.5, 255, 0, 0),
    #     mkpoint(0.5, 0.5, 0, 255, 0),
    #     mkpoint(1, 0.5, 0, 0, 255),
    #     mkline(0, 0, 1, 0, 255, 255, 255),
    #     mkline(0, 1, 1, 1, 255, 255, 255),
    # ]
    # key_points = [
    #     KeyLine(
    #         int(0 * width),
    #         int(0 * height),
    #         int(0 * width),
    #         int(1 * height),
    #         np.array([255, 0, 0]),
    #     ),
    #     KeyLine(
    #         int(0.5 * width),
    #         int(0 * height),
    #         int(0.5 * width),
    #         int(1 * height),
    #         np.array([0, 255, 0]),
    #     ),
    #     KeyLine(
    #         int(1 * width),
    #         int(0 * height),
    #         int(1 * width),
    #         int(1 * height),
    #         np.array([0, 0, 255]),
    #     ),
    # ]
    # key_points = [
    #     *mkspectrum(0, 0, 1, 1, 0, 1, n=10),
    # ]

    _, positions = solve_colors(shape, color_matrix, ColorSpace.CIELAB, key_objects)

    cover_res = features[0].image.width
    collage = Image.new("RGB", (width * cover_res, height * cover_res), "white")
    for i in range(height):
        for j in range(width):
            collage.paste(features[positions[j * height + i]].image, (j * cover_res, i * cover_res))

    collage.show()
