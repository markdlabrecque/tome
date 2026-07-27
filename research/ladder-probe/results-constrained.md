# Ladder probe results

Arms: qwen3:14b, qwen3:4b, gpt-oss:20b, qwen3:8b · control: `qwen3:14b` · 8 paired draws of 40.

## Quality

| model | ent/subj | coverage | fabric. | Decision recall | Fact share | distinct keys | schema fails |
|---|---|---|---|---|---|---|---|
| `qwen3:14b` | 1.01 | 99.1% | 0.0% | 101% | 12.8% | 39.4 | 0 |
| `qwen3:4b` | 0.95 | 92.5% | 0.0% | 89% | 13.6% | 37.8 | 0 |
| `gpt-oss:20b` | 0.00 | 0.0% | 0.0% | 0% | 0.0% | 0.0 | 8 |
| `qwen3:8b` | 0.27 | 26.2% | 0.0% | 27% | 16.0% | 10.6 | 0 |

## Paired difference from control (95% bootstrap CI, 10k resamples)

| model | Δ ent/subj | Δ coverage (pp) | verdict inputs |
|---|---|---|---|
| `qwen3:4b` | -0.056 [-0.162, +0.025] | -6.6 [-11.2, -2.5] | ent/subj 94% of control · coverage 93% |
| `gpt-oss:20b` | -1.006 [-1.050, -0.975] | -99.1 [-100.0, -97.8] | ent/subj 0% of control · coverage 0% |
| `qwen3:8b` | -0.741 [-0.962, -0.434] | -72.8 [-96.9, -38.4] | ent/subj 26% of control · coverage 26% |

## Cost (measured on the Fedora box, RX 6900 XT)

| model | wall/entry | prefill s | decode s | in tok | out tok | prefill share | truncated |
|---|---|---|---|---|---|---|---|
| `qwen3:14b` | 60.4s | 0.96 | 59.07 | 1264 | 2420 | 2% | 0 |
| `qwen3:4b` | 28.3s | 0.31 | 27.76 | 1258 | 2648 | 1% | 0 |
| `gpt-oss:20b` | 2.6s | 0.58 | 0.53 | 1139 | 40 | 52% | 0 |
| `qwen3:8b` | 38.2s | 0.75 | 35.71 | 1105 | 2269 | 2% | 2 |

## type_confidence against §13.4's 0.7 starting value

| model | n | mean | below 0.7 |
|---|---|---|---|
| `qwen3:14b` | 322 | 0.915 | 0.0% |
| `qwen3:4b` | 304 | 0.945 | 0.0% |
| `gpt-oss:20b` | 0 | — | — |
| `qwen3:8b` | 85 | 0.994 | 1.2% |
