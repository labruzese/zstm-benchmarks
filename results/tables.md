_Median of 5 trials. Throughput in committed transactions/second; higher is better. The small figure under each cell is that cell's max/min across trials -- `!` marks 1.25x or worse, where the run was too noisy for the median to mean much._


## Throughput


### Counter

| threads | zstm (ALA) | zstm vs RSTM |
|---:|---:|---:|
| 1 | 106,530,303<br><sub>1.06x</sub> | -- |
| 2 | 18,561,661<br><sub>1.19x</sub> | -- |
| 4 | 12,005,023<br><sub>1.19x</sub> | -- |
| 8 | 6,656,899<br><sub>1.05x</sub> | -- |
| 16 | 4,681,060<br><sub>1.17x</sub> | -- |

### ReadNWrite1/m256

| threads | zstm (ALA) | zstm vs RSTM |
|---:|---:|---:|
| 1 | 47,135,757<br><sub>1.01x</sub> | -- |
| 2 | 13,249,858<br><sub>1.16x</sub> | -- |
| 4 | 8,571,940<br><sub>!1.44x</sub> | -- |
| 8 | 8,355,629<br><sub>1.07x</sub> | -- |
| 16 | 7,271,555<br><sub>1.03x</sub> | -- |

### ReadNWrite1/m4096

| threads | zstm (ALA) | zstm vs RSTM |
|---:|---:|---:|
| 1 | 47,099,254<br><sub>1.01x</sub> | -- |
| 2 | 13,624,692<br><sub>1.14x</sub> | -- |
| 4 | 10,677,980<br><sub>!1.26x</sub> | -- |
| 8 | 7,444,399<br><sub>1.01x</sub> | -- |
| 16 | 6,551,930<br><sub>1.05x</sub> | -- |

### ReadWriteN/m256

| threads | zstm (ALA) | zstm vs RSTM |
|---:|---:|---:|
| 1 | 26,858,221<br><sub>1.03x</sub> | -- |
| 2 | 7,300,400<br><sub>!1.39x</sub> | -- |
| 4 | 5,265,278<br><sub>!2.00x</sub> | -- |
| 8 | 2,850,943<br><sub>!2.49x</sub> | -- |
| 16 | 2,231,026<br><sub>!2.65x</sub> | -- |

### Disjoint/16-8-2

| threads | zstm (ALA) | zstm vs RSTM |
|---:|---:|---:|
| 1 | 20,220,194<br><sub>1.00x</sub> | -- |
| 2 | 16,156,631<br><sub>1.06x</sub> | -- |
| 4 | 12,599,254<br><sub>1.11x</sub> | -- |
| 8 | 7,171,166<br><sub>1.23x</sub> | -- |
| 16 | 4,735,292<br><sub>1.13x</sub> | -- |

## Scaling (throughput relative to that config at 1 thread)


### Counter

| threads | zstm (ALA) |
|---:|---:|
| 1 | 1.00x |
| 2 | 0.17x |
| 4 | 0.11x |
| 8 | 0.06x |
| 16 | 0.04x |

### ReadNWrite1/m256

| threads | zstm (ALA) |
|---:|---:|
| 1 | 1.00x |
| 2 | 0.28x |
| 4 | 0.18x |
| 8 | 0.18x |
| 16 | 0.15x |

### ReadNWrite1/m4096

| threads | zstm (ALA) |
|---:|---:|
| 1 | 1.00x |
| 2 | 0.29x |
| 4 | 0.23x |
| 8 | 0.16x |
| 16 | 0.14x |

### ReadWriteN/m256

| threads | zstm (ALA) |
|---:|---:|
| 1 | 1.00x |
| 2 | 0.27x |
| 4 | 0.20x |
| 8 | 0.11x |
| 16 | 0.08x |

### Disjoint/16-8-2

| threads | zstm (ALA) |
|---:|---:|
| 1 | 1.00x |
| 2 | 0.80x |
| 4 | 0.62x |
| 8 | 0.35x |
| 16 | 0.23x |

## Abort rate (aborts per committed transaction)

_RSTM CGL is a single global lock and never aborts._


### Counter

| threads | zstm (ALA) |
|---:|---:|
| 1 | 0.000 |
| 2 | 0.202 |
| 4 | 0.234 |
| 8 | 0.614 |
| 16 | 0.798 |

### ReadNWrite1/m256

| threads | zstm (ALA) |
|---:|---:|
| 1 | 0.000 |
| 2 | 0.023 |
| 4 | 0.067 |
| 8 | 0.033 |
| 16 | 0.038 |

### ReadNWrite1/m4096

| threads | zstm (ALA) |
|---:|---:|
| 1 | 0.000 |
| 2 | 0.001 |
| 4 | 0.002 |
| 8 | 0.008 |
| 16 | 0.015 |

### ReadWriteN/m256

| threads | zstm (ALA) |
|---:|---:|
| 1 | 0.000 |
| 2 | 0.143 |
| 4 | 0.348 |
| 8 | 0.958 |
| 16 | 1.711 |

### Disjoint/16-8-2

| threads | zstm (ALA) |
|---:|---:|
| 1 | 0.000 |
| 2 | 0.000 |
| 4 | 0.000 |
| 8 | 0.000 |
| 16 | 0.000 |

## Measurement spread

_6 of 25 cells reached 1.25x max/min across 5 trials and are marked `!` above. Differences at or below a cell's own spread are not results._

| spread | workload | threads | config |
|---:|---|---:|---|
| 2.65x | ReadWriteN/m256 | 16 | zstm (ALA) |
| 2.49x | ReadWriteN/m256 | 8 | zstm (ALA) |
| 2.00x | ReadWriteN/m256 | 4 | zstm (ALA) |
| 1.44x | ReadNWrite1/m256 | 4 | zstm (ALA) |
| 1.39x | ReadWriteN/m256 | 2 | zstm (ALA) |
| 1.26x | ReadNWrite1/m4096 | 4 | zstm (ALA) |
