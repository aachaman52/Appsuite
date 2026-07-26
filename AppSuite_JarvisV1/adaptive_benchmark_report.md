# Adaptive Pipeline Benchmark Report
    
## Results
| Metric | Old Pipeline | Adaptive Pipeline |
|--------|-------------|-------------------|
| Success Rate | 29% | 67% |
| Avg Runtime | 0.129s | 0.157s |

## Optimization Decisions Triggered:
- Increased 'godot' timeout to 120s due to historical timeouts.
- Reduced asset count to 1 because Blender reliability is low (0.68).

## Worker Statistics Tracker:
- **internet**: Reliability 0.96, Runs: 200, Failures: 7
- **analysis**: Reliability 0.96, Runs: 193, Failures: 7
- **blender**: Reliability 0.67, Runs: 196, Failures: 62
- **godot**: Reliability 0.67, Runs: 144, Failures: 45
- **validation**: Reliability 1.00, Runs: 99, Failures: 0
- **deploy**: Reliability 0.97, Runs: 99, Failures: 3
