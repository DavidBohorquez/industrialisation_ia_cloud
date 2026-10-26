import pandas as pd

from livraison_express.core.features import FEATURE_COLUMNS, TARGET_COLUMN

REQUIRED_COLUMNS = {"order_id", "order_date", *FEATURE_COLUMNS, TARGET_COLUMN}

ESSENTIAL_COLUMNS = [
    "order_id",
    "distance_km",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
    TARGET_COLUMN,
]


def validate_dataset(df: pd.DataFrame) -> None:
    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Colonnes obligatoires absentes : {sorted(missing_columns)}"
        )

    if df["order_id"].duplicated().any():
        raise ValueError("Des identifiants de commande sont dupliqués.")

    if df[TARGET_COLUMN].isna().any():
        raise ValueError("La variable cible contient des valeurs manquantes.")

    if not df["hour"].between(0, 23).all():
        raise ValueError("Certaines heures sont invalides.")

    if not df["distance_km"].ge(0).all():
        raise ValueError("La distance ne peut pas être négative.")

    if not df["weight_kg"].ge(0).all():
        raise ValueError("Le poids ne peut pas être négatif.")

    if not df["preparation_time_min"].ge(0).all():
        raise ValueError("Le temps de préparation ne peut pas être négatif.")

    if not df["carrier_capacity"].between(0, 1).all():
        raise ValueError(
            "La capacité du transporteur doit être comprise entre 0 et 1."
        )

    if not df["stock_available"].isin([0, 1]).all():
        raise ValueError(
            "La variable stock_available doit contenir uniquement 0 ou 1."
        )


def clean_orders_data(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.drop_duplicates(subset=["order_id"], keep="last")
    cleaned = cleaned.assign(
        order_date=pd.to_datetime(cleaned["order_date"], errors="coerce")
    )
    cleaned = cleaned.dropna(subset=ESSENTIAL_COLUMNS)

    cleaned = cleaned[cleaned["distance_km"] >= 0]
    cleaned = cleaned[cleaned["weight_kg"] >= 0]
    cleaned = cleaned[cleaned["preparation_time_min"] >= 0]
    cleaned = cleaned[cleaned["carrier_capacity"].between(0, 1)]
    cleaned = cleaned[cleaned["stock_available"].isin([0, 1])]

    return cleaned.reset_index(drop=True)
