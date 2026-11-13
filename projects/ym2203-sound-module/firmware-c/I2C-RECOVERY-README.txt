Rev C C SDK 0.4.0-alpha.2 / I2C停止・通信休止・再開の総合確認 v1

実機結果
  2026-11-14、0.4.0-alpha.2の4区間がユーザー実機で合格。HOST PASS/DONE、
  2回の191件完走、リース停止185/191、音声fault=0、消音、左右正常を確認しました。
  以下は受入時の手順です。0.5版にも同じI2C v2の確認用として同梱します。

目的と所要時間
  受入済みalpha.2のまま、演奏中STOP、通信休止による1秒リース消音、
  読取りだけでは再開しないこと、明示的な再演奏を約70～90秒で確認します。
  既存のオリジナル音階・和音データ191件/13秒をI2C経由で使用します。
  Ys IIの楽曲ファイルも受入済みUF2も変更しません。基板の結線変更はありません。

1. 準備
  Rev Cは既に書込み済みのC=0.4.0-alpha.2をそのまま使用してください。
  USB操作画面でaudio_ready=1、fault=0、FM100%（fm_gain_eighths=8）を確認します。
  この確認のためのUF2書込み直しや、Ys II全曲の再試験は不要です。
  操作側Pico/Pico2のMicroPythonと結線は、全曲再生で成功した状態を維持します。
  hardware I2C0 / GP0=SDA / GP1=SCL / 100kHz / 0x42 / 3.3V信号。
  Rev C側GP20/21、共通GND、外部5V、LINE→AMS-22も従来どおりです。
  両方の音量を低めにし、USB操作画面はログ保存用に開いておきます。

2. 操作側へ配置
  ZIPのhost/music/recovery.bin →操作側Picoの /music/recovery.bin
  /music/song.bin（Ys II）はそのまま残します。
  /lib/ym2203_revc_stream.pyはalpha.2で全曲再生したものをそのまま使えます。
  ZIPのhost/libにも同じファイルを同梱しています（コード変更なし）。
  host/recovery_check.pyをPC上のThonnyで開き、操作側Picoを選んでF5実行します。
  main.pyとして保存する必要はありません。Rev C上でPythonを実行しないでください。

3. 自動で行う4区間
  開始前に5秒待ちます。各区間はFM音階→SSG音階→FM+SSGの6声和音の順です。
  音階は「ドレミファソファミレド」、各音に短い隙間があります。

  1/4 STOP:
    和音が始まって約0.5秒後にSTOP。旋律・伴奏を含む全音が消え、4秒間無音。
    この間は状態読取りだけを行い、残りの楽譜が進まないことも検査します。
  2/4 REPLAY:
    BEGIN→データ再送→PLAYにより、FM音階の先頭ドからSSG音階・和音まで全演奏。
    正常終了後に全音が消えます。Rev Cの再起動はしません。
  3/4 LEASE:
    同じ音階・和音を再生。和音開始約0.5秒後、KEEPを送り、操作側のI2Cを無効化し、
    GP0/1を入力へ戻して1800ms通信を休止します。物理ケーブルは抜きません。
    通信休止から約1秒で全音が自動消音。I2Cを再接続して状態だけを読み、さらに4秒間無音。
    この区間は意図的にRev Cへ「FAIL I2C error=8」を発生させます。
    error=8はリース失効の期待値です。STATUSの音声faultは0のままであることを確認します。
  4/4 RECOVERY:
    STOPでリース失効を解除し、0.5秒の停止確認後、BEGIN→データ再送→PLAY。
    再びFM音階の先頭ドからSSG音階・和音まで全演奏し、正常終了・最終STOPで無音になります。

  試験中、USB画面の再生・STOP・リセットなどを操作せず、自動進行を待ってください。
  音が大きすぎるなどで止める必要がある場合はUSB画面の全音停止を使えます。
  その場合は試験未完了として扱います。

4. 期待するHOST末尾
  RESULT: sections=4 completed=2 explicit_interruptions=1 lease_interruptions=1
  INTERRUPT: STOP executed=185 LEASE executed=185/191
  FINAL: state=4 error=0 queued=0 flags=0x03 audio_ok=1
  HOST PASS: STOP, lease mute, read-only reattachment and explicit restart verified
  DONE: target stopped; report both logs and the four audible sections
  HOST SAFE: GP0/GP1 inputs; target lease is fallback if STOP failed

  HOSTはI2C状態・件数・CRC・停止中の進捗を検査します。
  実際の音と物理ゲートの消音は、耳とRev C側ログを合わせて確認してください。
  Rev C側には2回のDONE I2C、意図的なFAIL I2C error=8が1回とSTOPが記録されます。
  最後にUSB画面で状態取得し、次を確認してください。
    STATUS C=0.4.0-alpha.2 audio_ready=1 fault=0 state=3 events=191/191 gates=0
    I2C protocol=2 address=0x42 state=4 result=0 error=0 ... executed=191/191 queued=0 ... sealed=0
  STATUSのstate=3はこの時点では停止を表します。fault=0と併せて判断します。
  以前のYs IIの123137件ではなく、今回の短い診断データ191件になります。

5. 報告する内容
  各区間のFM/SSG、左右、1/4と3/4の全音消音・4秒無音、2/4と4/4の先頭からの再演奏、
  歪み・予定外の音切れの有無を教えてください。
  HOST全ログと、Rev Cのerror=8前後・2回のDONE I2C・最後のSTATUS/AUDIO/I2Cを保存してください。
  この物理試験の0.4.0-alpha.2での受入は完了しています。0.5版は別途実機受入前です。

開発者向け再現手順（firmware-cディレクトリ）
  python3 -m unittest discover -s tests -v
  python3 tools/verify_host_micropython.py --micropython /path/to/micropython --recovery
  python3 tools/build_recovery_check.py --output ../outputs/revc-i2c-recovery-v1.zip
  モデル試験は実際のC処理とホストPythonを使用しますが、物理I2C/GPIO/アナログ音声の試験ではありません。
