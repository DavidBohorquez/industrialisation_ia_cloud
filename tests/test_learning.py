from livraison_express.core.features import FEATURE_COLUMNS, TARGET_COLUMN
from livraison_express.core.learning.ml_pipeline import MLPipeline
from livraison_express.core.learning.ml_trainer import MLTrainer
from livraison_express.core.learning.train_test_splitter import TrainTestSplitter


def test_pipeline_is_new_and_untrained_on_each_call():
    builder = MLPipeline(random_state=0)

    first, second = builder.get_model_pipeline(), builder.get_model_pipeline()

    assert first is not second
    assert not hasattr(first.named_steps["classifier"], "coef_")


def test_split_is_80_20_and_keeps_the_share_of_eligible_orders(orders):
    X_train, X_test, y_train, y_test = TrainTestSplitter(random_state=0).split(orders)

    assert len(X_test) == round(len(orders) * 0.20)
    assert list(X_train.columns) == FEATURE_COLUMNS
    assert abs(y_train.mean() - y_test.mean()) < 0.01
    assert abs(y_test.mean() - orders[TARGET_COLUMN].mean()) < 0.01


def test_split_never_gives_the_target_to_the_model(orders):
    X_train, X_test, _, _ = TrainTestSplitter(random_state=0).split(orders)

    assert TARGET_COLUMN not in X_train.columns
    assert "order_id" not in X_train.columns


def test_trainer_is_reproducible(orders):
    first = MLTrainer(random_state=0, evaluation_threshold=0.5).train(orders, "a")
    second = MLTrainer(random_state=0, evaluation_threshold=0.5).train(orders, "b")

    assert first.card.metrics == second.card.metrics


def test_metrics_follow_the_evaluation_threshold(orders):
    lenient = MLTrainer(random_state=0, evaluation_threshold=0.2).train(orders, "a").card.metrics
    strict = MLTrainer(random_state=0, evaluation_threshold=0.8).train(orders, "b").card.metrics

    assert strict["precision"] > lenient["precision"]
    assert strict["recall"] < lenient["recall"]
    assert strict["roc_auc"] == lenient["roc_auc"]


def test_trainer_reports_its_parameters():
    assert MLTrainer(random_state=7, evaluation_threshold=0.5).params == {
        "random_state": 7,
        "test_size": 0.20,
    }
