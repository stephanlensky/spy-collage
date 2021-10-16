import colorgram
import sklearn.cluster


def get_features(image_path):
    colors = colorgram.extract(image_path, 2)
    features = []
    for c in colors:
        features.extend(c.rgb)
    return features


def get_clusters(features, n):
    km = sklearn.cluster.KMeans(
        n_clusters=n, init="random", n_init=10, max_iter=300, tol=1e-04, random_state=0
    )
    km.fit_predict(features)
    print(km.cluster_centers_)
