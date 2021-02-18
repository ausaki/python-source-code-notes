# GIL

## 数据结构

### _gil_runtime_state

_gil_runtime_state 保存 GIL 相关的信息.

```c
// Include/internal/pycore_gil.h

struct _gil_runtime_state {
    /* microseconds (the Python API uses seconds, though) */
    unsigned long interval;
    /* Last PyThreadState holding / having held the GIL. This helps us
       know whether anyone else was scheduled after we dropped the GIL. */
    _Py_atomic_address last_holder;
    /* Whether the GIL is already taken (-1 if uninitialized). This is
       atomic because it can be read without any lock taken in ceval.c. */
    _Py_atomic_int locked;
    /* Number of GIL switches since the beginning. */
    unsigned long switch_number;
    /* This condition variable allows one or several threads to wait
       until the GIL is released. In addition, the mutex also protects
       the above variables. */
    PyCOND_T cond;
    PyMUTEX_T mutex;
#ifdef FORCE_SWITCHING
    /* This condition variable helps the GIL-releasing thread wait for
       a GIL-awaiting thread to be scheduled and take the GIL. */
    PyCOND_T switch_cond;
    PyMUTEX_T switch_mutex;
#endif
};

// Include/internal/pycore_runtime.h

typedef struct pyruntimestate {
    struct _ceval_runtime_state ceval;
} _PyRuntimeState;

struct _ceval_runtime_state {
    /* Request for checking signals. It is shared by all interpreters (see
       bpo-40513). Any thread of any interpreter can receive a signal, but only
       the main thread of the main interpreter can handle signals: see
       _Py_ThreadCanHandleSignals(). */
    _Py_atomic_int signals_pending;
    struct _gil_runtime_state gil;
};
```

关系链: `_PyRuntimeState` -> `_ceval_runtime_state` -> `_gil_runtime_state`.

### _ceval_state

_ceval_state 保存有 `gil_drop_request` 属性, `gil_drop_request` 和 GIL 有一点关系.

```c
// Include/internal/pycore_interp.h

struct _ceval_state {
    int recursion_limit;
    /* Records whether tracing is on for any thread.  Counts the number
       of threads for which tstate->c_tracefunc is non-NULL, so if the
       value is 0, we know we don't have to check this thread's
       c_tracefunc.  This speeds up the if statement in
       _PyEval_EvalFrameDefault() after fast_next_opcode. */
    int tracing_possible;
    /* This single variable consolidates all requests to break out of
       the fast path in the eval loop. */
    _Py_atomic_int eval_breaker;
    /* Request for dropping the GIL */
    _Py_atomic_int gil_drop_request;
    struct _pending_calls pending;
};

struct _is {
  struct _ceval_state ceval
}
```

PyInterpreterState 包含 _ceval_state.



## 获取和释放 GIL


### ceval 执行字节码时检查 GIL

```c
//Python/ceval.c

PyObject* _Py_HOT_FUNCTION
_PyEval_EvalFrameDefault(PyThreadState *tstate, PyFrameObject *f, int throwflag)
{
main_loop:
    for (;;) {
        assert(stack_pointer >= f->f_valuestack); /* else underflow */
        assert(STACK_LEVEL() <= co->co_stacksize);  /* else overflow */
        assert(!_PyErr_Occurred(tstate));

        /* Do periodic things.  Doing this every time through
           the loop would add too much overhead, so we do it
           only every Nth instruction.  We also do it if
           ``pending.calls_to_do'' is set, i.e. when an asynchronous
           event needs attention (e.g. a signal handler or
           async I/O handler); see Py_AddPendingCall() and
           Py_MakePendingCalls() above. */

        if (_Py_atomic_load_relaxed(eval_breaker)) {
            opcode = _Py_OPCODE(*next_instr);
            if (opcode == SETUP_FINALLY ||
                opcode == SETUP_WITH ||
                opcode == BEFORE_ASYNC_WITH ||
                opcode == YIELD_FROM) {
                /* Few cases where we skip running signal handlers and other
                   pending calls:
                   - If we're about to enter the 'with:'. It will prevent
                     emitting a resource warning in the common idiom
                     'with open(path) as file:'.
                   - If we're about to enter the 'async with:'.
                   - If we're about to enter the 'try:' of a try/finally (not
                     *very* useful, but might help in some cases and it's
                     traditional)
                   - If we're resuming a chain of nested 'yield from' or
                     'await' calls, then each frame is parked with YIELD_FROM
                     as its next opcode. If the user hit control-C we want to
                     wait until we've reached the innermost frame before
                     running the signal handler and raising KeyboardInterrupt
                     (see bpo-30039).
                */
                goto fast_next_opcode;
            }

            if (eval_frame_handle_pending(tstate) != 0) {
                goto error;
            }
        }
    }
}

static int
eval_frame_handle_pending(PyThreadState *tstate)
{
    _PyRuntimeState * const runtime = &_PyRuntime;
    struct _ceval_runtime_state *ceval = &runtime->ceval;
    
    /* GIL drop request */
    if (_Py_atomic_load_relaxed(&ceval2->gil_drop_request)) {
        /* Give another thread a chance */
        if (_PyThreadState_Swap(&runtime->gilstate, NULL) != tstate) {
            Py_FatalError("tstate mix-up");
        }
        drop_gil(ceval, ceval2, tstate);

        /* Other threads may run now */

        take_gil(tstate);

        if (_PyThreadState_Swap(&runtime->gilstate, tstate) != NULL) {
            Py_FatalError("orphan tstate");
        }
    }
    return 0;
}
```

### take_gil 和 drop_gil

```c
// Python/ceval_gil.h

static void
drop_gil(struct _ceval_runtime_state *ceval, struct _ceval_state *ceval2,
         PyThreadState *tstate)
{
    struct _gil_runtime_state *gil = &ceval->gil;
    if (!_Py_atomic_load_relaxed(&gil->locked)) {
        Py_FatalError("drop_gil: GIL is not locked");
    }

    /* tstate is allowed to be NULL (early interpreter init) */
    if (tstate != NULL) {
        /* Sub-interpreter support: threads might have been switched
           under our feet using PyThreadState_Swap(). Fix the GIL last
           holder variable so that our heuristics work. */
        _Py_atomic_store_relaxed(&gil->last_holder, (uintptr_t)tstate);
    }

    MUTEX_LOCK(gil->mutex);
    _Py_ANNOTATE_RWLOCK_RELEASED(&gil->locked, /*is_write=*/1);
    _Py_atomic_store_relaxed(&gil->locked, 0);
    COND_SIGNAL(gil->cond);
    MUTEX_UNLOCK(gil->mutex);

#ifdef FORCE_SWITCHING
    if (_Py_atomic_load_relaxed(&ceval2->gil_drop_request) && tstate != NULL) {
        MUTEX_LOCK(gil->switch_mutex);
        /* Not switched yet => wait */
        if (((PyThreadState*)_Py_atomic_load_relaxed(&gil->last_holder)) == tstate)
        {
            assert(is_tstate_valid(tstate));
            RESET_GIL_DROP_REQUEST(tstate->interp);
            /* NOTE: if COND_WAIT does not atomically start waiting when
               releasing the mutex, another thread can run through, take
               the GIL and drop it again, and reset the condition
               before we even had a chance to wait for it. */
            COND_WAIT(gil->switch_cond, gil->switch_mutex);
        }
        MUTEX_UNLOCK(gil->switch_mutex);
    }
#endif
}

/* Take the GIL.

   The function saves errno at entry and restores its value at exit.

   tstate must be non-NULL. */
static void
take_gil(PyThreadState *tstate)
{
    int err = errno;

    assert(tstate != NULL);

    if (tstate_must_exit(tstate)) {
        /* bpo-39877: If Py_Finalize() has been called and tstate is not the
           thread which called Py_Finalize(), exit immediately the thread.

           This code path can be reached by a daemon thread after Py_Finalize()
           completes. In this case, tstate is a dangling pointer: points to
           PyThreadState freed memory. */
        PyThread_exit_thread();
    }

    assert(is_tstate_valid(tstate));
    PyInterpreterState *interp = tstate->interp;
    struct _ceval_runtime_state *ceval = &interp->runtime->ceval;
    struct _ceval_state *ceval2 = &interp->ceval;
    struct _gil_runtime_state *gil = &ceval->gil;

    /* Check that _PyEval_InitThreads() was called to create the lock */
    assert(gil_created(gil));

    MUTEX_LOCK(gil->mutex);

    if (!_Py_atomic_load_relaxed(&gil->locked)) {
        goto _ready;
    }

    while (_Py_atomic_load_relaxed(&gil->locked)) {
        unsigned long saved_switchnum = gil->switch_number;

        unsigned long interval = (gil->interval >= 1 ? gil->interval : 1);
        int timed_out = 0;
        COND_TIMED_WAIT(gil->cond, gil->mutex, interval, timed_out);

        /* If we timed out and no switch occurred in the meantime, it is time
           to ask the GIL-holding thread to drop it. */
        
        /* 我觉得这里检查 gil->switch_number == saved_switchnum 的原因:
           在当前线程阻塞在 COND_TIMED_WAIT 期间, 有可能其它线程获取了 GIL, 导致 gil->switch_number 增加 1.
           如果此时当前线程不检查 gil->switch_number == saved_switchnum 而直接设置 gil_drop_request, 那么可能导致刚刚获得 GIL 的线程立刻又释放 GIL.
           频繁的 GIL 切换会影响解释器的吞吐量, 
        */
        if (timed_out &&
            _Py_atomic_load_relaxed(&gil->locked) &&
            gil->switch_number == saved_switchnum)
        {
            if (tstate_must_exit(tstate)) {
                MUTEX_UNLOCK(gil->mutex);
                PyThread_exit_thread();
            }
            assert(is_tstate_valid(tstate));

            SET_GIL_DROP_REQUEST(interp);
        }
    }

_ready:
#ifdef FORCE_SWITCHING
    /* This mutex must be taken before modifying gil->last_holder:
       see drop_gil(). */
    MUTEX_LOCK(gil->switch_mutex);
#endif
    /* We now hold the GIL */
    _Py_atomic_store_relaxed(&gil->locked, 1);
    _Py_ANNOTATE_RWLOCK_ACQUIRED(&gil->locked, /*is_write=*/1);

    if (tstate != (PyThreadState*)_Py_atomic_load_relaxed(&gil->last_holder)) {
        _Py_atomic_store_relaxed(&gil->last_holder, (uintptr_t)tstate);
        ++gil->switch_number;
    }

#ifdef FORCE_SWITCHING
    COND_SIGNAL(gil->switch_cond);
    MUTEX_UNLOCK(gil->switch_mutex);
#endif

    if (tstate_must_exit(tstate)) {
        /* bpo-36475: If Py_Finalize() has been called and tstate is not
           the thread which called Py_Finalize(), exit immediately the
           thread.

           This code path can be reached by a daemon thread which was waiting
           in take_gil() while the main thread called
           wait_for_thread_shutdown() from Py_Finalize(). */
        MUTEX_UNLOCK(gil->mutex);
        drop_gil(ceval, ceval2, tstate);
        PyThread_exit_thread();
    }
    assert(is_tstate_valid(tstate));

    if (_Py_atomic_load_relaxed(&ceval2->gil_drop_request)) {
        RESET_GIL_DROP_REQUEST(interp);
    }
    else {
        /* bpo-40010: eval_breaker should be recomputed to be set to 1 if there
           is a pending signal: signal received by another thread which cannot
           handle signals.

           Note: RESET_GIL_DROP_REQUEST() calls COMPUTE_EVAL_BREAKER(). */
        COMPUTE_EVAL_BREAKER(interp, ceval, ceval2);
    }

    /* Don't access tstate if the thread must exit */
    if (tstate->async_exc != NULL) {
        _PyEval_SignalAsyncExc(tstate);
    }

    MUTEX_UNLOCK(gil->mutex);

    errno = err;
}
```

## 总结

假设当前持有 GIL 正在运行的线程为 A, 而另一个阻塞在 GIL 的线程为 B.

A 在执行字节码的过程中会不断检查 `gil_drop_request`, 如果 `gil_drop_request` 为真, 那么说明有其它线程想要获取 GIL. 

A 发现 `gil_drop_request` 为真, 立马调用 `drop_gil` 释放 GIL, 其实释放 GIL 的内部过程就是将 `gil->locked` 设为 0, 同时通知阻塞在 `gil->cond` 的线程. A 释放 GIL 后, 接着调用 `take_gil` 从而阻塞在 GIL 上.

B 被唤醒, 获取到 GIL 然后开始执行.

一个线程在尝试获取 GIL 时, 会等待 `gil->cond` 并设置超时时间, 如果超时说明当前持有 GIL 的线程没有主动释放 GIL, 那么该线程会设置 `gil_drop_request`, 然后又开始等待 `gil->cond`.

等待时间等于 `gil->interval`, 该值可以通过 `sys.setswitchinterval` 设置.

线程阻塞在 GIL 的时间并不是准确(或大致)等于 `gil->interval`, 有几个原因会影响阻塞时间:

- 每个字节码需要的时间不一样. 线程刚设置 `gil_drop_request`, 当前持有 GIL 线程正好已经开始执行下一跳字节码了, 错过了检查 `gil_drop_request` 的时机. 因此该线程需要多等待一个字节码的时间.

- 解释器并不是每执行完一条字节码就回到循环的开头. 解释器为了提升执行效率对执行字节码的流程进行了各种优化. 例如, 当执行完当前字节码后, 立马跳转到下一条字字节码的地址, 跳过了检查 `gil_drop_request` 的代码.

- 如果有多个线程在等待 GIL, 此时哪个线程能够获取 GIL 是不确定的, 取决于操作系统的进程调度. 可能一个线程等待时间远小于 `gil->interval` 却获取了 GIL, 而另一个等待了很久的线程却没有获取 GIL.

由于 GIL 的存在, 同一时刻只能有一个线程拥有解释器的执行权. 另外, GIL 还影响了操作系统的进程调度, 然而 Python 却没有实现自己的调度系统.

### 来自 Python/ceval_gil.h 的注释

```
/*
   Notes about the implementation:

   - The GIL is just a boolean variable (locked) whose access is protected
     by a mutex (gil_mutex), and whose changes are signalled by a condition
     variable (gil_cond). gil_mutex is taken for short periods of time,
     and therefore mostly uncontended.

   - In the GIL-holding thread, the main loop (PyEval_EvalFrameEx) must be
     able to release the GIL on demand by another thread. A volatile boolean
     variable (gil_drop_request) is used for that purpose, which is checked
     at every turn of the eval loop. That variable is set after a wait of
     `interval` microseconds on `gil_cond` has timed out.

      [Actually, another volatile boolean variable (eval_breaker) is used
       which ORs several conditions into one. Volatile booleans are
       sufficient as inter-thread signalling means since Python is run
       on cache-coherent architectures only.]

   - A thread wanting to take the GIL will first let pass a given amount of
     time (`interval` microseconds) before setting gil_drop_request. This
     encourages a defined switching period, but doesn't enforce it since
     opcodes can take an arbitrary time to execute.

     The `interval` value is available for the user to read and modify
     using the Python API `sys.{get,set}switchinterval()`.

   - When a thread releases the GIL and gil_drop_request is set, that thread
     ensures that another GIL-awaiting thread gets scheduled.
     It does so by waiting on a condition variable (switch_cond) until
     the value of last_holder is changed to something else than its
     own thread state pointer, indicating that another thread was able to
     take the GIL.

     This is meant to prohibit the latency-adverse behaviour on multi-core
     machines where one thread would speculatively release the GIL, but still
     run and end up being the first to re-acquire it, making the "timeslices"
     much longer than expected.
     (Note: this mechanism is enabled with FORCE_SWITCHING above)
*/
```

