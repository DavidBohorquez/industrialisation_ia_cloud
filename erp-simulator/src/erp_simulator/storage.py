"""Adaptateurs de persistance du simulateur ERP."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time

import psycopg
from contracts import Order
from psycopg.rows import dict_row
from pymongo import MongoClient, UpdateOne

# Colonnes d'une commande, dans l'ordre de la table (sans le résultat express_eligible).
ORDER_COLUMNS = (
    "order_id, order_date, hour, day_of_week, weekend, distance_km, order_value_eur, "
    "weight_kg, stock_available, preparation_time_min, carrier_capacity, weather, "
    "delivery_zone, customer_type"
)


class PostgresWriter:
    def __init__(self, dsn: str) -> None:
        self.connection = psycopg.connect(dsn, row_factory=dict_row)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY, order_date DATE, hour INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL, weekend INTEGER,
            distance_km DOUBLE PRECISION NOT NULL, order_value_eur DOUBLE PRECISION NOT NULL,
            weight_kg DOUBLE PRECISION NOT NULL, stock_available INTEGER NOT NULL,
            preparation_time_min DOUBLE PRECISION, carrier_capacity DOUBLE PRECISION NOT NULL,
            weather TEXT NOT NULL, delivery_zone TEXT NOT NULL, customer_type TEXT NOT NULL,
            express_eligible SMALLINT)"""
        )
        self.connection.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_date DATE")
        self.connection.execute("ALTER TABLE orders ALTER COLUMN weekend DROP NOT NULL")
        self.connection.execute("ALTER TABLE orders ALTER COLUMN preparation_time_min DROP NOT NULL")
        # Résultat de la commande (oublié dans le sujet) : NULL tant qu'il n'est pas connu.
        self.connection.execute(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS express_eligible SMALLINT"
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            description TEXT NOT NULL)"""
        )
        self.connection.execute(
            """INSERT INTO schema_migrations (version, description) VALUES
            (2015, 'Ajout de la colonne weekend'),
            (2017, 'Ajout de la colonne preparation_time_min'),
            (2023, 'Extension du schéma pour le flux courant'),
            (2026, 'Ajout de la colonne express_eligible (résultat de la commande)')
            ON CONFLICT (version) DO NOTHING"""
        )
        self.connection.commit()

    def write(self, orders: Sequence[Order]) -> int:
        inserted = 0
        with self.connection.transaction():
            for order in orders:
                columns = tuple(order)
                cursor = self.connection.execute(
                    f"INSERT INTO orders ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))}) ON CONFLICT (order_id) DO NOTHING",
                    tuple(order[column] for column in columns),
                )
                inserted += cursor.rowcount
        self.connection.commit()
        return inserted

    def count_from(self, start: date, end: date) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM orders WHERE order_date >= %s AND order_date < %s",
            (start, end),
        ).fetchone()
        self.connection.commit()
        return int(row["count"])

    def next_sequence(self) -> int:
        row = self.connection.execute(
            """SELECT COALESCE(MAX(
                CASE WHEN order_id ~ '^ERP-[0-9]+$'
                THEN SUBSTRING(order_id FROM 5)::BIGINT ELSE 0 END
            ), 0) AS max_sequence FROM orders"""
        ).fetchone()
        self.connection.commit()
        return int(row["max_sequence"])

    def last_order_date(self) -> date | None:
        row = self.connection.execute("SELECT MAX(order_date) AS last_date FROM orders").fetchone()
        self.connection.commit()
        return row["last_date"]

    def pending_outcomes(self, known_until: date) -> list[Order]:
        rows = self.connection.execute(
            f"""SELECT {ORDER_COLUMNS} FROM orders
            WHERE express_eligible IS NULL AND preparation_time_min IS NOT NULL
            AND order_date <= %s ORDER BY order_id""",
            (known_until,),
        ).fetchall()
        self.connection.commit()
        return rows

    def set_outcomes(self, outcomes: Mapping[str, int]) -> int:
        updated = 0
        with self.connection.transaction():
            for order_id, outcome in outcomes.items():
                # La garde IS NULL rend l'écriture idempotente : un résultat connu ne change plus.
                cursor = self.connection.execute(
                    """UPDATE orders SET express_eligible = %s
                    WHERE order_id = %s AND express_eligible IS NULL""",
                    (outcome, order_id),
                )
                updated += cursor.rowcount
        self.connection.commit()
        return updated

    def close(self) -> None:
        self.connection.close()


class MongoWriter:
    def __init__(self, uri: str) -> None:
        self.client = MongoClient(uri)
        self.client.admin.command("ping")
        self.collection = self.client["livraison_express"]["orders"]
        self.collection.create_index("order_id", unique=True)

    @staticmethod
    def _document(order: Order) -> Order:
        document = dict(order)
        if isinstance(document.get("order_date"), date):
            document["order_date"] = datetime.combine(document["order_date"], time.min)
        # Champ présent dès l'insertion, comme la colonne NULL de PostgreSQL.
        document.setdefault("express_eligible", None)
        return document

    def write(self, orders: Sequence[Order]) -> int:
        if not orders:
            return 0
        # Insertion seulement si la commande est absente (comme ON CONFLICT DO NOTHING côté
        # PostgreSQL) : le ReplaceOne du sujet effaçait le résultat déjà connu au redémarrage.
        result = self.collection.bulk_write([
            UpdateOne(
                {"order_id": order["order_id"]},
                {"$setOnInsert": self._document(order)},
                upsert=True,
            )
            for order in orders
        ])
        return result.upserted_count

    def set_outcomes(self, outcomes: Mapping[str, int]) -> int:
        if not outcomes:
            return 0
        # Sans upsert : les commandes d'avant 2023 n'existent pas dans MongoDB et ne doivent
        # pas y être créées. Le filtre None correspond aussi à un champ absent.
        result = self.collection.bulk_write([
            UpdateOne(
                {"order_id": order_id, "express_eligible": None},
                {"$set": {"express_eligible": outcome}},
            )
            for order_id, outcome in outcomes.items()
        ])
        return result.modified_count

    def close(self) -> None:
        self.client.close()
