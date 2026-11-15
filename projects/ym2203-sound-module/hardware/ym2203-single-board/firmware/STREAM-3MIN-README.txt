YM2203 Rev C / alpha.2 / 3分間ストリーミング確認 v1
2026-11-13

今回の目的
----------
常用ファームウェアalpha.2で、128枠のキューを補充しながら180秒分・726イベントを演奏する。
基本サンプル2回の演奏は実機合格済み。今回はキュー容量を超える継続運転と正常終了を確認する。
実施前には常用版の受入確認を今回を含め残り2件と定めた。今回は実機合格済み。
残り1件の停止・通信復帰の総合確認後、USB-MIDI実装へ移る。
組立・実現性確認の診断一式を再実行する必要はない。

実行
----
1. Rev Cは前回と同じalpha.2のまま動かし、READYを確認する。
   既にREADY後の待機中なら、そのまま使用できる。Rev C側のファイル更新は不要。
   手動起動の場合はCtrl+D後に次を実行する。
       from ym2203_hw import run
       run()
2. 操作側Picoでは前回の /lib/ym2203_revc.py をそのまま使用する。
   今回の host/endurance.py をThonnyで開いて実行する。Rev C側には実行しない。
   main.pyとしての保存は不要。配線・電源・音量は前回合格時の設定を使う。
3. 初期設定とキュー先読みの数秒後に発音が始まり、約3分間演奏する。
   完了までHOST側に30秒間隔の表示が出る。Rev C側は音声取り込み中にログを出さない。

音の期待値
----------
FMの「ド・ミ・休符・ソ・休符・ミ・レ・休符・ド・休符」を36回繰り返す。
各枠は500ms、1周5秒。休符中もSSGの低い和音は持続する。
1周の最後にも休符があるため、前周の最後のドと次周の最初のドはつながらない。
演奏終了時にFM・SSGとも停止する。左右は同じ音。
意図したFM旋律の休符と、予定外の全音の途切れを区別して確認する。

HOSTログの期待値
----------------
  YM2203 alpha.2 / three-minute streaming HOST / OTHER Pico only
  ...
  STREAM 1/6 elapsed_ms=約30000 queued=... seq=...
  STREAM 2/6 elapsed_ms=約60000 queued=... seq=...
  ...
  STREAM 6/6 elapsed_ms=約180000 queued=... seq=...
  STREAM COMPLETE events=726 score_ms=180000 host_elapsed_ms=...
  FINAL STATE seq=... result=0 flags=1 queued=0
  HOST PASS: three-minute replenished score,normal end and explicit STOP
  DONE: ...
queuedとseqはI2C応答の進み方で変わるため固定しない。seqは255の次に0へ戻る。
score_msは登録譜面上の正確な期間。host_elapsed_msは初期キュー送信や準備/終了処理も含むため
180000より長くなる。30秒表示はHOSTのPLAY完了応答からの経過時間であり、ADC測定ではない。
終了時のresult=0 / flags=1 / queued=0はACK成功・READYのみ・予約なしを意味する。
このプログラムは常用ホストライブラリのstream()をそのまま使う。イベント全体をRAMに展開しない。

終了と報告
----------
Rev Cの常用サーバーは演奏終了後も待機を続けるため、通常はSAFE/DONEを表示しない。
Rev CをCtrl+Cで止めた場合にSAFEとKeyboardInterruptが出るのは通常の停止操作。
HOSTの完了ログ、約3分継続したこと、旋律の休符と伴奏、左右、歪み/予定外の音切れ、終了後の無音を報告する。
新ファームウェアはdeadline missesを外部APIへ公開していないため、未取得のカウンタを0と推定しない。
異常時はHOSTの例外全文を保存し、Rev CもCtrl+Cで停止して末尾ログを保存する。

検証の範囲
----------
この追加プログラムは、実際のホストmain()と現行alpha.2エンジンを接続するモデル検証で、
726イベント、180000msの予定時刻、30秒ごとの進行表示、ACK周回、正常終了と全音停止を確認する。
I2C待ち5/30msとYM書き込み4.4msはモデル値であり、実機での最大時間を保証しない。
MicroPython WASMは実際のPython互換性を検証するが、GPIO/PIO/DMA/音質はモデルで代用する。
2026-11-13、ユーザー実機で3分間完走。休符・伴奏・終了後消音、左右正常、
歪み/予定外の音切れなし、HOST PASS・DONEを確認した。個別カウンタの全文は未提出。
