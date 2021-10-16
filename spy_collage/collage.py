import math

import colorgram
import sklearn.cluster
from PIL import Image
from scipy.spatial import distance


def get_features(image_path):
    colors = colorgram.extract(image_path, 2)
    features = []
    for c in colors:
        features.extend(c.rgb)
    return tuple(features)


def get_clusters(features, n):
    km = sklearn.cluster.KMeans(
        n_clusters=n, init="random", n_init=10, max_iter=300, tol=1e-04, random_state=0
    )
    km.fit_predict(features)
    return km.cluster_centers_


def sort_features_by_distance(features: list, p):
    features.sort(key=lambda p2: distance.euclidean(p, p2))


def row_collage(features: list, features_to_path: dict[tuple, str]):
    features_to_image: dict[tuple, Image.Image] = {}
    for f, p in features_to_path.items():
        features_to_image[f] = Image.open(p)
    cover_res = features_to_image[features[0]].width

    collage_size_x = math.ceil(math.sqrt(len(features)))
    collage_size_y = collage_size_x

    collage = Image.new("RGB", (collage_size_x * cover_res, collage_size_y * cover_res), "white")

    for i, f in enumerate(features):
        img = features_to_image[f]
        collage.paste(img, ((i % collage_size_x) * cover_res, (i // collage_size_y) * cover_res))

    collage.show()
