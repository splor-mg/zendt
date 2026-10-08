import pandas as pd
import pytest

from zendt.engine import evaluate
from zendt.errors import EngineError
from zendt.models import RuleEntry


def score_graph(column: str, expression: str = 'amount + 1') -> dict:
    return {
        'nodes': [
            {'id': 'input', 'name': 'Request', 'type': 'inputNode'},
            {
                'id': 'expr',
                'name': 'score',
                'type': 'expressionNode',
                'content': {
                    'expressions': [
                        {'id': 'e', 'key': column, 'value': expression}
                    ],
                },
            },
            {'id': 'output', 'name': 'Response', 'type': 'outputNode'},
        ],
        'edges': [
            {'id': 'e1', 'sourceId': 'input', 'targetId': 'expr'},
            {'id': 'e2', 'sourceId': 'expr', 'targetId': 'output'},
        ],
    }


def identity_graph() -> dict:
    return {
        'nodes': [
            {'id': 'input', 'name': 'Request', 'type': 'inputNode'},
            {'id': 'output', 'name': 'Response', 'type': 'outputNode'},
        ],
        'edges': [{'id': 'e1', 'sourceId': 'input', 'targetId': 'output'}],
    }


def entry(
    name: str, source_id: str = 'rules', key: str | None = None
) -> RuleEntry:
    return RuleEntry(name, source_id, f'/tmp/{name}.json', key or name)


@pytest.fixture(autouse=True)
def reset_engine():
    evaluate.close_pool()
    evaluate._WORKER_ENGINE = None
    evaluate._WORKER_COMPILED = None
    yield
    evaluate.close_pool()
    evaluate._WORKER_ENGINE = None
    evaluate._WORKER_COMPILED = None


def test_evaluate_input_appends_new_columns_and_keeps_the_delimiter():
    frame = pd.DataFrame({'amount': [1, 2]})
    frame.attrs['delimiter'] = ';'
    result = evaluate.evaluate_input(
        frame,
        [entry('flag')],
        {'rules': {'flag': score_graph('scored')}},
    )

    assert list(result.columns) == ['amount', 'scored']
    assert result['scored'].tolist() == [2, 3]
    assert result.attrs['delimiter'] == ';'


def test_a_later_rule_reads_the_original_input():
    frame = pd.DataFrame({'amount': [10]})
    with pytest.raises(EngineError, match='row 1'):
        evaluate.evaluate_input(
            frame,
            [entry('first'), entry('second')],
            {
                'rules': {
                    'first': score_graph('scored'),
                    'second': score_graph('again', 'scored + 1'),
                }
            },
        )


def test_repeated_new_columns_are_rejected():
    frame = pd.DataFrame({'amount': [1]})
    with pytest.raises(EngineError, match='repeats columns'):
        evaluate.evaluate_input(
            frame,
            [entry('first'), entry('second')],
            {
                'rules': {
                    'first': score_graph('scored'),
                    'second': score_graph('scored'),
                }
            },
        )


def test_columns_already_on_the_input_are_not_appended():
    frame = pd.DataFrame({'amount': [4, 5]})
    result = evaluate.evaluate_input(
        frame,
        [entry('flag')],
        {'rules': {'flag': identity_graph()}},
    )
    assert list(result.columns) == ['amount']
    assert result['amount'].tolist() == [4, 5]


def test_rules_from_two_sources_are_compiled_separately():
    frame = pd.DataFrame({'amount': [1]})
    result = evaluate.evaluate_input(
        frame,
        [entry('a', 'one', 'a'), entry('b', 'two', 'b')],
        {
            'one': {'a': score_graph('from_a')},
            'two': {'b': score_graph('from_b', 'amount + 2')},
        },
    )
    assert result['from_a'].tolist() == [2]
    assert result['from_b'].tolist() == [3]


def test_missing_loaded_source():
    frame = pd.DataFrame({'amount': [1]})
    with pytest.raises(EngineError, match='no loaded source'):
        evaluate.evaluate_input(frame, [entry('flag')], {})


def test_empty_input_stays_empty():
    frame = pd.DataFrame({'amount': pd.Series(dtype='int64')})
    result = evaluate.evaluate_input(
        frame,
        [entry('flag')],
        {'rules': {'flag': score_graph('scored')}},
    )
    assert list(result.columns) == ['amount']
    assert len(result) == 0


def test_row_failure_names_the_input_row():
    frame = pd.DataFrame({'amount': [1, 2]})
    with pytest.raises(EngineError, match='row 1'):
        evaluate.evaluate_input(
            frame,
            [entry('flag')],
            {'rules': {'flag': score_graph('scored', 'missing + 1')}},
        )


def test_batches_walk_the_table_in_order():
    frame = pd.DataFrame({'amount': [1, 2, 3]})
    evaluate.init_engine({'flag': score_graph('scored')})
    added = evaluate.evaluate_batches(frame, 'flag', batch_size=1)
    assert added['scored'].tolist() == [2, 3, 4]


def test_engine_must_be_initialized_and_batch_size_positive():
    frame = pd.DataFrame({'amount': [1]})
    with pytest.raises(EngineError, match='not initialized'):
        evaluate.evaluate_batches(frame, 'flag')
    evaluate.init_engine({'flag': score_graph('scored')})
    with pytest.raises(EngineError, match='Batch size'):
        evaluate.evaluate_batches(frame, 'flag', batch_size=0)


def test_init_engine_rejects_a_map_that_is_not_jdm():
    with pytest.raises(EngineError, match='map of zen key'):
        evaluate.init_engine(['nope'])
    with pytest.raises(EngineError, match='Cannot compile'):
        evaluate.init_engine({'flag': {'foo': 1}})


def test_init_engine_reports_a_zen_compile_error():
    with pytest.raises(EngineError, match='could not be compiled'):
        evaluate.init_engine({
            'flag': {'nodes': [{'type': 'nope'}], 'edges': []}
        })


def test_resolve_n_jobs_stays_single_process_below_the_threshold(monkeypatch):
    monkeypatch.setattr(evaluate.os, 'cpu_count', lambda: 16)
    assert evaluate.resolve_n_jobs(evaluate.PARALLEL_MIN_ROWS - 1) == 1
    assert (
        evaluate.resolve_n_jobs(evaluate.PARALLEL_MIN_ROWS)
        == evaluate.DEFAULT_MAX_JOBS
    )


def test_resolve_n_jobs_never_exceeds_the_machine(monkeypatch):
    monkeypatch.setattr(evaluate.os, 'cpu_count', lambda: 2)
    assert evaluate.resolve_n_jobs(evaluate.PARALLEL_MIN_ROWS) == 2
    monkeypatch.setattr(evaluate.os, 'cpu_count', lambda: None)
    assert evaluate.resolve_n_jobs(evaluate.PARALLEL_MIN_ROWS) == 1


def test_parallel_evaluation_keeps_nullable_integers(monkeypatch):
    monkeypatch.setattr(evaluate, 'resolve_n_jobs', lambda n_rows: 2)
    frame = pd.DataFrame({'amount': pd.Series([1, 2, 3, 4], dtype='Int64')})
    result = evaluate.evaluate_input(
        frame,
        [entry('flag')],
        {'rules': {'flag': score_graph('scored')}},
    )
    assert result['scored'].tolist() == [2, 3, 4, 5]
    evaluate.close_pool()


def test_parallel_evaluation_keeps_row_order(monkeypatch):
    monkeypatch.setattr(evaluate, 'resolve_n_jobs', lambda n_rows: 2)
    frame = pd.DataFrame({'amount': [1, 2, 3, 4]})
    result = evaluate.evaluate_input(
        frame,
        [entry('flag')],
        {'rules': {'flag': score_graph('scored')}},
    )
    assert result['scored'].tolist() == [2, 3, 4, 5]
    evaluate.close_pool()


def test_parallel_failure_closes_the_pool(monkeypatch):
    monkeypatch.setattr(evaluate, 'resolve_n_jobs', lambda n_rows: 2)
    frame = pd.DataFrame({'amount': [1, 2, 3, 4]})
    with pytest.raises(EngineError, match='row'):
        evaluate.evaluate_input(
            frame,
            [entry('flag')],
            {'rules': {'flag': score_graph('scored', 'missing + 1')}},
        )
    assert evaluate._POOL is None


def test_row_result_and_failure_detail():
    assert (
        evaluate.failure_detail({
            'error': {'type': 'NodeError', 'source': 'boom'}
        })
        == 'NodeError: boom'
    )
    assert evaluate.failure_detail({'error': 'plain'}) == 'plain'
    assert evaluate.failure_detail(None) == 'evaluation failed'
    with pytest.raises(EngineError, match='non-object'):
        evaluate.row_result(
            {'success': True, 'data': {'result': [1]}}, 'flag', 3
        )
    with pytest.raises(EngineError, match='row 3'):
        evaluate.row_result({'success': False, 'error': 'nope'}, 'flag', 3)


def test_returned_row_count_must_match(monkeypatch):
    frame = pd.DataFrame({'amount': [1, 2]})

    def short(df, key, batch_size=evaluate.DEFAULT_BATCH_SIZE):
        return pd.DataFrame({'scored': [1]})

    monkeypatch.setattr(evaluate, 'evaluate_batches', short)
    with pytest.raises(EngineError, match='returned 1 rows'):
        evaluate.evaluate_input(
            frame, [entry('flag')], {'rules': {'flag': score_graph('scored')}}
        )
