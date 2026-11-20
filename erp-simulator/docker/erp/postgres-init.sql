-- Exécuté une seule fois par l'image postgres, au premier démarrage (volume vide),
-- avec l'utilisateur POSTGRES_USER (livraison).
--
-- Ce fichier est monté par docker-compose.erp.yml mais manquait dans le sujet fourni.
-- La table orders n'est pas créée ici : le simulateur s'en charge
-- (storage.PostgresWriter._ensure_schema), pour garder une seule définition du schéma.

-- Rôle de l'application de machine learning : lecture seule (ADR-0009).
-- Mot de passe de l'environnement de test uniquement ; en production, le rôle et son
-- secret sont fournis par l'administrateur de la base.
CREATE ROLE ml_reader LOGIN PASSWORD 'ml_reader';
GRANT CONNECT ON DATABASE livraison_express TO ml_reader;
GRANT USAGE ON SCHEMA public TO ml_reader;
-- La table orders n'existe pas encore : les droits s'appliqueront aux tables que le
-- simulateur créera ensuite avec l'utilisateur livraison.
ALTER DEFAULT PRIVILEGES FOR ROLE livraison IN SCHEMA public GRANT SELECT ON TABLES TO ml_reader;
-- Deuxième barrière : toute transaction de ce rôle est en lecture seule.
ALTER ROLE ml_reader SET default_transaction_read_only = on;
