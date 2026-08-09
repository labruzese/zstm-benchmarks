/**
 *  BENCHMARK PATCH -- not part of upstream RSTM v7.
 *
 *  The array/counter microbenchmarks store `int` (4 bytes). On x86-64 that is a
 *  sub-word access, so RSTM's library API routes it through the
 *  `DISPATCH<T,4>` specialization in include/api/library_inst.hpp: a masked
 *  read-modify-write, logged at 8-byte word granularity. Two adjacent elements
 *  therefore share one log entry and conflict with each other even when the
 *  program touches distinct indices.
 *
 *  zstm's TxWord is a native usize, so it has no equivalent behavior. Comparing
 *  the two as-is would measure RSTM's sub-word dispatch, not the NOrec
 *  implementations.
 *
 *  Parameterizing the element type lets us build both:
 *
 *    - default (`int`)                : stock RSTM, kept as the reference point
 *    - -DBENCH_ELEM_T=intptr_t        : word-sized, apples-to-apples with zstm
 */

#ifndef BENCH_ELEM_HPP__
#define BENCH_ELEM_HPP__

#include <stdint.h>

#ifndef BENCH_ELEM_T
#define BENCH_ELEM_T int
#endif

#endif // BENCH_ELEM_HPP__
