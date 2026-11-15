YM2203 Rev C / alpha.2 / 最後の停止・通信復帰総合確認 v1
2026-11-13

前提と終了条件
--------------
alpha.2の基本サンプル2回と、180秒/726イベントの補充式再生はユーザー実機で合格済み。
今回が常用I2C版の受入確認の最後の1件。合格後はUSB-MIDI実装へ移る。
Rev Cのファームウェア、HOSTのym2203_revc.py、GPIO割り当て、配線、給電、音量は前回と同じ。
今回追加する実行ファイルは HOSTの host/recovery.py だけ。

実行手順
--------
1. Rev Cはalpha.2のREADY後の待機状態にする。既に動いていればそのまま使用できる。
   手動起動する場合だけCtrl+D後に次を実行する。
       from ym2203_hw import run
       run()
2. 操作側Picoで host/recovery.py をThonnyに開き、実行する。Rev C側で実行しない。
   HOST /lib/ym2203_revc.py は前回のまま。main.pyやboot.pyへの保存は不要。
3. 約30秒前後の4区間を聴く。通信・初期設定時間により所要時間は前後する。
   ケーブルの抜き差し、電源再投入、手動リセットは行わない。
   両音量は前回合格時の低めの設定から開始する。

4区間の期待値
-------------
1/4 旋律の途中STOP
  FMのドレミファソファミレド＋SSG和音を開始し、約1.2秒後にSTOPする。
  音階の途中で全テスト音が消え、その後4秒間は再発音しない。
  HOSTは状態の読み取りだけを行い、残りの予約が再開しないことを確認する。
2/4 先頭からの完奏
  同じ譜面を再送し、FM全9音をドから、SSG伴奏付きで約4.5秒間演奏する。
  終了後は全テスト音が消える。
3/4 通信休止と再接続
  再び途中まで演奏し、HOSTのGP0/GP1を入力へ切り替えて1800ms通信を休止する。
  この区間はKEEP、STOP、状態読み取りも一切行わない。
  通信休止から約1秒で全音が自動消音する。
  I2Cを再設定して同じRev Cへ再接続し、識別子・変わらないseq・期限消音を検証する。
  接続しただけでは再発音しない。状態読み取りだけでさらに4秒間消音を保つ。
4/4 明示操作での復帰
  STOPで期限切れ状態を解除し、同じ譜面を再送・PLAYする。
  FM全9音とSSG伴奏を先頭から演奏し、最後は全テスト音を停止する。

現行APIではSTOP/通信期限切れ時に残りの予約は破棄する。
ここでの再演奏は、保持された音色を使い、同じ譜面を改めて送信する処理。
1/4と3/4の途中停止の音数は、通信の進み方で変わるため固定しない。
L/Rは同じ音。予定した停止や通信期限消音と、予定外の音切れを区別して確認する。

ログの期待値
------------
  1/4 PASS STOP / result=0 flags=1 queued=0 /4s read-only quiet
  2/4 PASS complete score and normal end
  HOST RELEASE / no I2C for1800ms;no KEEP,STOP or reads
  REBIND / seq=... result=5 flags=33 queued=0 / expect4s quiet
  3/4 PASS lease cleanup,same target sequence,read-only reattachment stayed muted
  4/4 PASS full recovery score and normal end
  FINAL STATE seq=... result=0 flags=1 queued=0
  HOST PASS: STOP,4s quiet,replay,HOST release,lease mute,quiet rebind and explicit recovery
  DONE: ...
再接続直後のresult=5 / flags=33は、期待どおりの通信期限切れ・消音状態。
STOP後の最終値はresult=0 / flags=1(READYのみ) / queued=0になる。
seqの値は固定しない。HOSTの状態検証は、聴感やアナログ出力の測定を代替しない。

停止と報告
----------
正常終了時、Rev Cの常用サーバーは待機を続けるためSAFE/DONEは表示しない。
HOSTの4区間のログとHOST PASS・DONE、4秒無音が2回あったこと、再演奏が先頭から全9音だったこと、
通信休止時の自動消音、左右と音質、終了後の消音を報告する。
途中エラー時はログ全文を保存する。Rev CをCtrl+Cで止めた場合はSAFEと例外末尾も保存する。
HOSTを通信休止中にCtrl+Cで止めても、finallyでI2Cを再接続してSTOPを試みる。
再接続自体が失敗した場合は、既存の通信リースが消音を担う。自動再演奏は行わない。

確認の範囲
----------
対象は、トランザクション完了後のHOST端子解放/再設定と通信休止からの復帰。
物理断線、SDA/SCL固定、途中バイトでの中断、Rev Cの電源再投入、電源投入時の自動起動は
このHOSTプログラムでは確認しない。GPIOは従来のHOST GP0/GP1だけを使用する。
CPythonと実MicroPython WASMで現行ドライバー/エンジンを接続し、STOP、4秒読み取り専用待機、
1800msの無通信、期限消音後の読み取り専用再接続、誤った状態/識別子/seqで再演奏しないこと、
端子解放中の割り込み時の復旧を検証する。GPIO/音質/電気的タイミングはモデルで代用する。
2026-11-13、ユーザー実機で全4区間合格。途中STOP後/再接続後4秒消音、
通信期限による自動消音、先頭から全9音の再演奏、左右正常、歪み/予定外の音切れなし、
HOST PASS・DONEを確認した。常用I2C版の受入確認は完了。USB-MIDI実装へ移行した。
