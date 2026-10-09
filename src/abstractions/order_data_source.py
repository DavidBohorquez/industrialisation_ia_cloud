from abc import ABC, abstractmethod

import pandas as pd


class OrderDataSource(ABC):
    @abstractmethod
    def load_orders(self) -> pd.DataFrame: ...
