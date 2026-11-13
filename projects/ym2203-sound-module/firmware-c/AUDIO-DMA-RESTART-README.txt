YM2203 Rev C C0.5.0-alpha.3 / MIDI発音準備の音声再起動修正

今回のログ
  alpha.1で「単独音も和音も出ない」と報告があり、CDCはaudio_ready=0、fault=16、
  AUDIO blocks=2、peak=0、gates=0でした。これは音声DMA起動時のFIFO先行充填失敗です。
  MIDI単独音のNote Off後に和音を落とすalpha.2の修正とは別の問題です。
  alpha.2を経由する必要はありません。今回のalpha.3は両方の修正を含みます。

修正内容
  連鎖DMAは、停止する全チャンネルのENを先に下げてからabortします。
  旧コードはENを下げずに1個ずつabortしており、RP2350-E5の対策がありませんでした。
  PIO FIFOと転送記述子を初期化した後、DMAのDREQ要求カウンタをクリアして
  周辺回路とのハンドシェイクを更新し、チャンネルを再有効化します。
  再生中の音声パイプラインは125→108、2ブロック/4.5msを維持します。
  FM受信PIO、PCM変換、ゲイン、音程表、GPIO、I2C v2と操作側ライブラリは変更しません。
  起動の1msタイムアウトと実行中の異常停止は維持し、異常データを無視して継続しません。

検証と限界
  実際のaudio.c、audio_start.c、新DMAライフサイクル処理をモデル内で実行します。
  abort後にDREQ要求が残る条件では旧コードがfault16になり、修正版は
  5種類の停止位相で各32回の再起動を完了しました。
  DMA先行充填が本当に失敗する条件では、修正版でもfault16で停止して診断状態を保存します。
  これはソフトウェアモデルです。ユーザーの旧ログにはDMA内部レジスタがないため、
  実機のfault16が発生した詳細な内部タイミングを確定したとは扱いません。

実機再確認（2026-11-14）
  ユーザーからalpha.3で6つの単独音と和音保持、audio_ready=1/fault=0、
  左右正常・歪み/音切れなしの報告を受領しました。この報告にCDC生ログは含まれません。
  次はMIDI-I2C-HANDOVER-README.txtの総合確認です。現在のalpha.3を書き直す必要はありません。

更新と最小の再確認（実施済み手順を保存）
  1. 両方の音量を下げ、CDC全音停止を実行し、BOOTSELで今回のrevc-c.uf2をコピーします。
     fault16の状態はSTOPだけでは復旧しません。今回の書き込みによる再起動が必要です。
  2. CDCへ接続し、STATUS C=0.5.0-alpha.3、audio_ready=1、fault=0を確認します。
     MIDI確認画面も同梱のpc/usb-midi-test.htmlへ更新して再読み込みし、接続先を選び直します。
  3. ボタン1を1回押します。6つの単独音が順番に鳴り、最後の6声和音が持続することを確認します。
     和音中にCDCで状態取得し、audio_ready=1、fault=0、MIDI owned=1、mask=63を確認してください。
     MIDI全音停止で消音し、gates=0になることを確認します。
  4. まずこの結果とCDCログを送ってください。HOSTの制御権切替試験はこの再確認が通ってから行います。
     操作側のファイル更新、配線変更、Ys II全曲再試験は今回不要です。

もし再発した場合
  繰り返し再生せず、STATUS/AUDIO/FAIL/MIDIに加え、TXSTARTとTXDMA行を保存してください。
  fault16では、停止処理で消える前のFIFO深さ、DMA制御・残件数・DREQ状態をこれらに記録します。
  診断のDMA配列の順序はRX0/RX1/TX0/TX1です。USBや音声ケーブルを抜く必要はありません。

一次資料（ビルドはSDK2.2.0を固定）
  https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2_common/hardware_dma/include/hardware/dma.h
  dma_channel_abortのRP2350-E5に関する記載: abort前に対象と連鎖先のENをクリアすること。
  https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/dma.h
  CHx_DBG_CTDREQ: 書込みで要求カウンタをクリアし、DREQハンドシェイクを再開する。
