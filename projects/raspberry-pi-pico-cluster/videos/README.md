# 実機実験の進捗動画

Raspberry Pi 5側managerが記録した完成画像、tile到着時刻、tile座標を使い、実際の到着順と時間を再構成したMP4です。カメラ映像や音声は含みません。

| 動画 | node数 | 長さ | SHA-256 |
| --- | ---: | ---: | --- |
| [`mandelbrot-progress-1-node.mp4`](mandelbrot-progress-1-node.mp4) | 1 | 30.63秒 | `3b38ee4d700aa85de1dbfc87d88536319743d35eabdfc2358628ddff6f5cd6ff` |
| [`mandelbrot-progress-3-nodes.mp4`](mandelbrot-progress-3-nodes.mp4) | 3 | 11.03秒 | `4496f9421dad61af05a6394eac7e0cc16883abf8be35e08d7515c0e66775bec9` |
| [`mandelbrot-progress-6-nodes.mp4`](mandelbrot-progress-6-nodes.mp4) | 6 | 6.33秒 | `1bcedcf564f1675498c1214de33e1b4e1068d55c2c7d404b963ebf42b990ac90` |
| [`raytracing-progress-original-1-node.mp4`](raytracing-progress-original-1-node.mp4) | 1 | 208.97秒 | `27a3278aac1de04593d68d7929ba19859bfe15ac2a3e4a40ba9a211c8d663de4` |
| [`raytracing-progress-original-3-nodes.mp4`](raytracing-progress-original-3-nodes.mp4) | 3 | 71.10秒 | `35df404104885b11e3af838f4dd96cf7406e85d8bfc5311b86c5b1ee185a0408` |
| [`raytracing-progress-original-6-nodes.mp4`](raytracing-progress-original-6-nodes.mp4) | 6 | 37.10秒 | `0ea59250da303d2d6d5ecdea2c1c61388f14595f75c3577bea6d09eae844fc39` |
| [`raytracing-progress-native-6-nodes.mp4`](raytracing-progress-native-6-nodes.mp4) | 6 | 32.27秒 | `2b02d148df24791082d300a12eba346719147cd51d558be0362b07af426bd655` |

最後の動画は最速だったnative emitter版です。それ以外のレイトレーシング動画はoriginal bytecode版です。動画末尾には完成状態を確認するためのhold時間が含まれるため、動画長はmanagerのE2E測定値より少し長くなります。

同じ形式のtraceはmanagerの`--record-trace`で作成し、`mandelbrot/network/render_progress_video.py`でMP4へ変換できます。元traceは実行ごとに大きくなるため本リポジトリには収録していません。
