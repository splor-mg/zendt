import atexit
import json
import math
import os
from multiprocessing import get_context

import pandas as pd
import zen

from zendt.errors import EngineError

DEFAULT_BATCH_SIZE = 20_000
DEFAULT_MAX_JOBS = 8
PARALLEL_MIN_ROWS = 10_000

_WORKER_ENGINE = None
_WORKER_COMPILED = None
_POOL = None
_POOL_SIZE = None
_POOL_RULES = None


def init_engine(rules_content):
    """Compile one source's `{zen key: JDM}` map.

    Keep the engine in this process.
    """
    global _WORKER_ENGINE, _WORKER_COMPILED
    if not isinstance(rules_content, dict):
        raise EngineError('Engine rules must be a map of zen key to JDM.')

    compiled = {}
    for key, body in rules_content.items():
        if (
            not isinstance(body, dict)
            or 'nodes' not in body
            or 'edges' not in body
        ):
            raise EngineError(
                f"Cannot compile '{key}'. Pass one source's JDM map, "
                'not the map of sources.'
            )
        try:
            compiled[key] = zen.ZenDecisionContent(json.dumps(body))
        except Exception as exc:
            raise EngineError(
                f"Rule '{key}' could not be compiled: {exc}"
            ) from exc

    def loader(rule_key):
        return _WORKER_COMPILED[rule_key]

    _WORKER_COMPILED = compiled
    _WORKER_ENGINE = zen.ZenEngine({'loader': loader})


def init_worker(rules_content):
    """Compile rules inside a spawned worker.

    Pin numeric libraries to one thread.
    """
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
    init_engine(rules_content)


def close_pool():
    """Close the worker pool, if this process owns one."""
    global _POOL, _POOL_SIZE, _POOL_RULES
    if _POOL is not None:
        _POOL.close()
        _POOL.join()
        _POOL = None
        _POOL_SIZE = None
        _POOL_RULES = None


atexit.register(close_pool)


def get_pool(n_jobs, rules_content):
    """Reuse the pool for an unchanged worker count and rule map."""
    global _POOL, _POOL_SIZE, _POOL_RULES
    if (
        _POOL is not None
        and _POOL_SIZE == n_jobs
        and _POOL_RULES is rules_content
    ):
        return _POOL
    close_pool()
    ctx = get_context('spawn')
    _POOL = ctx.Pool(
        processes=n_jobs,
        initializer=init_worker,
        initargs=(rules_content,),
    )
    _POOL_SIZE = n_jobs
    _POOL_RULES = rules_content
    return _POOL


def resolve_n_jobs(n_rows):
    """One process below PARALLEL_MIN_ROWS rows.

    Otherwise up to DEFAULT_MAX_JOBS, and never more cores than the
    machine has.
    """
    cpu = os.cpu_count() or 1
    if n_rows < PARALLEL_MIN_ROWS:
        return 1
    return max(1, min(cpu, DEFAULT_MAX_JOBS))


def failure_detail(result):
    error = result.get('error') if isinstance(result, dict) else None
    if isinstance(error, dict):
        kind = error.get('type') or 'Error'
        source = (
            error.get('source') or error.get('message') or json.dumps(error)
        )
        return f'{kind}: {source}'
    if error:
        return str(error)
    return 'evaluation failed'


def row_result(result, key, row_number):
    if (
        not isinstance(result, dict)
        or result.get('success') is False
        or 'data' not in result
    ):
        detail = failure_detail(result)
        raise EngineError(
            f"Rule '{key}' failed on input row {row_number}: {detail}"
        )
    data = result['data']
    row = data.get('result') if isinstance(data, dict) else None
    if not isinstance(row, dict):
        raise EngineError(
            f"Rule '{key}' returned a non-object result on input "
            f'row {row_number}.'
        )
    return row


def merge_rule_columns(table, produced):
    """Overwrite columns this rule repeated and append the rest.

    A repeated column stays where it is. The rule's values replace the
    cells already there, whether those cells came from the input or from
    an earlier rule. New columns are appended in the order the rule
    returned them. When several rules write the same name, the last
    write is the one that remains.
    """
    if len(produced.columns) == 0:
        return table
    fresh = [
        column
        for column in produced.columns
        if column not in table.columns
    ]
    for column in produced.columns:
        if column not in table.columns:
            continue
        replacement = produced[column].reset_index(drop=True)
        replacement.index = table.index
        table[column] = replacement
    if not fresh:
        return table
    return pd.concat([table, produced.loc[:, fresh]], axis=1)


def evaluate_batches(df, key, batch_size=DEFAULT_BATCH_SIZE):
    """Evaluate `key` in this process.

    The engine must already be compiled with `init_engine`.
    """
    if _WORKER_ENGINE is None:
        raise EngineError('Engine is not initialized.')
    if batch_size < 1:
        raise EngineError('Batch size must be at least 1.')

    out_chunks = []
    n = len(df)
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        batch = df.iloc[start:end]
        rows = batch.to_dict(orient='records')
        requests = [{'key': key, 'context': row} for row in rows]
        try:
            results = _WORKER_ENGINE.evaluate_batch(requests)
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(
                f"Rule '{key}' failed during evaluation: {exc}"
            ) from exc
        out_chunks.append(
            pd.DataFrame([
                row_result(result, key, start + offset + 1)
                for offset, result in enumerate(results)
            ])
        )
        del rows, requests, results

    if not out_chunks:
        return pd.DataFrame()
    return pd.concat(out_chunks, ignore_index=True)


def eval_chunk(job):
    """Evaluate one slice in a worker.

    Return every column the rule produced, including names already on
    the input. The parent overwrites those and appends the new ones.
    """
    key, chunk, batch_size = job
    out = evaluate_batches(chunk, key, batch_size)
    payload = {col: out[col].copy() for col in out.columns}
    return len(chunk), payload


def evaluate_parallel(
    df, key, n_jobs, rules_content, batch_size=DEFAULT_BATCH_SIZE
):
    """Split the table across workers.

    Returns every column the rule produced, in input order.
    """
    n = len(df)
    if n == 0:
        return pd.DataFrame()
    workers = max(1, min(int(n_jobs), n))
    chunk_size = math.ceil(n / workers)
    jobs = [
        (key, df.iloc[start : start + chunk_size].copy(), batch_size)
        for start in range(0, n, chunk_size)
    ]
    pool = get_pool(len(jobs), rules_content)
    try:
        parts = pool.map(eval_chunk, jobs)
    except EngineError:
        close_pool()
        raise
    except Exception as exc:
        close_pool()
        raise EngineError(
            f"Rule '{key}' failed during evaluation: {exc}"
        ) from exc
    if not parts:
        return pd.DataFrame()
    frames = []
    for n_rows, payload in parts:
        if payload:
            frames.append(pd.DataFrame(payload))
        else:
            frames.append(pd.DataFrame(index=range(n_rows)))
    return pd.concat(frames, ignore_index=True)


def evaluate_input(input_data, entries, loaded_rules):
    """Run each rule on the original rows.

    Append columns the rule created. Overwrite a column it repeats.

    The CLI chooses the worker count. One worker stays in this process, because
    spawning a pool for it costs more than it saves. Each rule sees the input
    table, so a later rule does not read columns produced by an earlier one.
    A later rule can still replace those columns in the result: the last
    rule to write a name is the one that remains.
    """
    n_jobs = resolve_n_jobs(len(input_data))
    table = input_data.reset_index(drop=True).copy()
    active_source = object()

    for entry in entries:
        try:
            rules_content = loaded_rules[entry.source_id]
        except KeyError:
            raise EngineError(
                f"Rule '{entry.ref}' has no loaded source."
            ) from None

        if n_jobs == 1:
            if active_source != entry.source_id:
                init_engine(rules_content)
                active_source = entry.source_id
            produced = evaluate_batches(input_data, entry.key)
        else:
            produced = evaluate_parallel(
                input_data, entry.key, n_jobs, rules_content
            )

        if len(produced) != len(input_data):
            raise EngineError(
                f"Rule '{entry.ref}' returned {len(produced)} rows "
                f'for {len(input_data)} input rows.'
            )
        table = merge_rule_columns(table, produced.reset_index(drop=True))

    table.attrs['delimiter'] = input_data.attrs.get('delimiter', ',')
    return table
