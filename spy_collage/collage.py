from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import colorgram
import imagehash  # type: ignore
import numpy as np
from PIL import Image
from skimage import color as spaces

from spy_collage.color_problem import ColorMatrix, ColorSpace, KeyObject, solve_colors


@dataclass
class ImageFeatures:
    features: np.ndarray
    image_path: Path
    __image: Optional[Image.Image]
    __image_phash: Optional[imagehash.ImageHash]

    def is_likely_duplicate(self, f: ImageFeatures) -> bool:
        return np.array_equal(self.features, f.features) and (self.image_phash == f.image_phash)

    @property
    def image(self):
        if self.__image is None:
            self.__image = Image.open(self.image_path)
        return self.__image

    @property
    def image_phash(self):
        if self.__image_phash is None:
            self.__image_phash = imagehash.phash(self.image)
        return self.__image_phash

    def to_dict(self):
        return {"features": list(self.features), "image_path": str(self.image_path)}

    @staticmethod
    def from_dict(d: dict):
        return ImageFeatures(np.asarray(d["features"]), Path(d["image_path"]), None, None)


def get_features(image_path) -> ImageFeatures:
    colors: list[colorgram.Color] = colorgram.extract(image_path, 1)
    features = []
    for c in colors:
        rgb = list(c.rgb)
        lab = spaces.rgb2lab(rgb)
        features.extend(lab)
    return ImageFeatures(np.asarray(features), image_path, None, None)


def lap_collage(
    features: list[ImageFeatures], shape: tuple[int, int], key_objects: list[KeyObject]
):
    width, height = shape
    color_matrix = ColorMatrix(np.asarray([f.features for f in features]), ColorSpace.CIELAB)
    _, positions = solve_colors(shape, color_matrix, ColorSpace.CIELAB, key_objects)

    cover_res = features[0].image.width
    collage = Image.new("RGB", (width * cover_res, height * cover_res), "white")
    for i in range(height):
        for j in range(width):
            collage.paste(features[positions[j * height + i]].image, (j * cover_res, i * cover_res))

    collage.show()
