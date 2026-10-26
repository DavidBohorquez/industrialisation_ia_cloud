import pandas as pd
from sklearn.model_selection import train_test_split

from livraison_express.core.features import FEATURE_COLUMNS, TARGET_COLUMN


class TrainTestSplitter:
    """Stratified split: the test set keeps the same share of eligible orders as the data."""

    def __init__(self, random_state: int, test_size: float = 0.20):
        self.random_state = random_state
        self.test_size = test_size

    def split(
        self, orders: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        X_train, X_test, y_train, y_test = train_test_split(
            orders[FEATURE_COLUMNS],
            orders[TARGET_COLUMN],
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=orders[TARGET_COLUMN],
        )
        return X_train, X_test, y_train, y_test
