# Ladder probe results

Arms: qwen3:14b, qwen3:8b, qwen3:4b · control: `qwen3:14b` · 8 paired draws of 40.

## Quality

| model | ent/subj | coverage | fabric. | Decision recall | Fact share | distinct keys | schema fails |
|---|---|---|---|---|---|---|---|
| `qwen3:14b` | 0.97 | 98.4% | 0.0% | 100% | 11.8% | 39.0 | 0 |
| `qwen3:8b` | 0.62 | 62.5% | 0.0% | 62% | 22.1% | 25.0 | 0 |
| `qwen3:4b` | 0.00 | 0.0% | 0.0% | 0% | 0.0% | 0.0 | 8 |

## Paired difference from control (95% bootstrap CI, 10k resamples)

| model | Δ ent/subj | Δ coverage (pp) | verdict inputs |
|---|---|---|---|
| `qwen3:8b` | -0.350 [-0.694, -0.097] | -35.9 [-69.7, -11.2] | ent/subj 64% of control · coverage 63% |
| `qwen3:4b` | -0.975 [-0.994, -0.950] | -98.4 [-100.0, -95.9] | ent/subj 0% of control · coverage 0% |

## Cost (measured on the Fedora box, RX 6900 XT)

| model | wall/entry | prefill s | decode s | in tok | out tok | prefill share | truncated |
|---|---|---|---|---|---|---|---|
| `qwen3:14b` | 60.1s | 1.53 | 57.07 | 1264 | 2346 | 3% | 0 |
| `qwen3:8b` | 41.3s | 0.86 | 39.13 | 1264 | 2507 | 2% | 0 |
| `qwen3:4b` | 46.1s | 0.47 | 44.60 | 1258 | 4096 | 1% | 8 |

## type_confidence against §13.4's 0.7 starting value

| model | n | mean | below 0.7 |
|---|---|---|---|
| `qwen3:14b` | 312 | 0.915 | 0.0% |
| `qwen3:8b` | 200 | 0.979 | 0.0% |
| `qwen3:4b` | 0 | — | — |
