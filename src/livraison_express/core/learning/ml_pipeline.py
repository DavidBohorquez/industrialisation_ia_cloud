from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from livraison_express.core.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES


class MLPipeline:
    """Builds an untrained pipeline: the same preprocessing at training and prediction time."""

    def __init__(self, random_state: int):
        self._random_state = random_state

    def get_model_pipeline(self) -> Pipeline:
        classifier = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=self._random_state,
        )
        return Pipeline(
            steps=[
                ("preprocessor", self._preprocessor()),
                ("classifier", classifier),
            ]
        )

    @staticmethod
    def _preprocessor() -> ColumnTransformer:
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )

        categorical_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )

        return ColumnTransformer(
            transformers=[
                ("numeric", numeric_transformer, NUMERIC_FEATURES),
                ("categorical", categorical_transformer, CATEGORICAL_FEATURES),
            ]
        )
