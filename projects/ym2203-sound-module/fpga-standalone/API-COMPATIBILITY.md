# WebLab・Rev C・F1のAPI互換計画

2026-11-14。新しい公開APIを確定する仕様ではなく、現状の差分と実装契約の草案。
F1の初版wire互換先は[Rev C C版I2C v2](../firmware-c/protocol-v2.md)とする。
WebLabのコード、既存Rev Cのwire、署名、ファームウェアをこの段階では変更しない。

## 互換の層を分ける

| 層 | 目標と現在の差分 |
| --- | --- |
| 楽曲データ | WYM1 header16 byte、event6 byte、絶対ms・同時刻の順序を共有。まず4 MHz、131071件まで |
| ホストPython API | 同じ呼出し・引数・返り値・停止の意味を目指す。backend選択や接続設定は分離する |
| wire | F1はまずC v2を保ち、RevCStream／既存HOST playerを再利用する。WebLabのwireを自動的にv2とは扱わない |
| USB-MIDI | MIDI1..3=FM3声、4..6=SSG3声、Note On/Offとpanic、所有権を比較する |
| 音響 | 同じ音符・音色・順序が目標。アナログ特性やWebAudioと実機のbit単位一致をAPI互換条件にしない |

## 調査した現状

| 項目 | WebLab | Rev C C版 | F1の進め方 |
| --- | --- | --- | --- |
| 接続 | 仮想machine.I2C、既定0x44 | 実I2C、0x42 | backend別。自動アドレス変更や旧署名への書込みをしない |
| 識別・status | 先頭version=1、6 byte、queued／volume | YM22S002、64 byte、state／CRC等 | v2を実装。共通statusはadapterで正規化する草案 |
| 即時操作 | write_register／fm_tone／fm_note／fm_off／ssg_note／ssg_off等 | v2はWYM1 sessionが中心。USB-MIDI操作は別系統 | 共通APIの即時系は後段。短い曲への変換だけで即時発音互換と主張しない |
| 予約 | reserve／reserve_score／reserve_mml、全件予約＋開始 | 1024件リングを補充、BEGIN／PUSH／PLAY／KEEP／SEAL | 楽譜→レジスタ生成はホスト側で共用し、転送と補充をbackendへ分離 |
| ファイル再生 | YM2203BinPlayer.play／play_raw／stop | RevCStream.play_file／stop、HOST playlist | 共通ホスト層にファイル再生とplaylistを寄せる。初版は既存playerを維持 |
| リピート | 仮想側に有界loopを渡す | HOST側から再送・再開 | hostで扱う共通経路とgapの能力差を明示。無音無しloopを黙って保証しない |
| 音量 | volume(percent)はFM＋SSG共通の仮想出力gain | fm 0..16はFMのみ。SSGは実アナログ、主音量は物理つまみ | 総音量とFM balanceを別能力にする。SSGレジスタ音量の上書きで代用しない |
| reset／stop | resetは予約を破棄、FM tone設定等の状態にも影響 | STOPでqueue破棄・ゲートOFF、次はBEGIN | STOP／chip reset／panicの意味を明示してから共通化 |
| clock | 現行note計算とBINは4 MHz前提 | 現行v2は4 MHzのみ | v2は4 MHz固定で維持。可変clockはcapabilityと版付き拡張で追加する |
| 生レジスタ | 仮想APIとemulatorの対応範囲 | C版は許可リスト・mask検査 | 共通安全subsetを定義し、unsupportedは明示拒否。SSG I/O等を暗黙に許可しない |

調査元：WebLabのsrc/drivers/web_lab_ym2203*_v1.py、src/devices/ym2203-prototype.ts、
src/audio/ym2203-protocol.ts、およびこのプロジェクトのfirmware-c。
WebLab確認時のHEADはd504cb2bdc1ab29a6cee63115e9e87c962184ed3。
reference/weblabは移行時スナップショットなので、現在のWebLab全APIの正本とみなさない。

## F1で先に守るC v2の契約

- 同じ0x42、YM22S002、64-byte snapshot＋CRC、要求最大208 byte、payload最大192 byte。
- 32件ずつのPUSH、queue1024、prefill min(512,total)、PLAYは250 ms後開始。
- 全イベントの時刻非減少・同時刻順序を保持。禁止レジスタと件数制限を変更しない。
- headerと全eventのCRCをSEAL時に照合し、period終了で全音停止してDONE。
- 重複は直前成功フレームの全バイト一致だけACK。再実行・lease延長をしない。
- 不正要求はnext_seqを消費しない。STOPのsequence再同期条件も既存Cに合わせる。
- 1秒lease。読取り／PING／重複／不正要求は延長しない。期限判定を要求受理より先に行う。
- faultとコマンドresultを分ける。STOP→BEGIN／再転送なしにfaultから復帰させない。
- BEGINのMIDI所有中拒否、I2C所有中のMIDI拒否、global STOP、USB再接続時の無音を維持する。
- USB reset／suspend／切断とI2C session resetを分離する。MIDI所有時の切断は消音する。
- API稼働やCRC正常とaudio_okを混同しない。音声が未実装の試作はaudio_okを偽って立てない。

新しい機能のためにYM22S002のpayloadやstatusを密かに拡張しない。
追加版・署名・capabilityの方法は公開API変更として別途設計する。

## 共通APIの移行順序

1. F1 v2 sessionを、既存RevCStream／Cモデルと同じ入力で試験する。
2. WYM1の再生・STOP・statusを対象に、backendを注入できる共通ホスト層を設計する。
3. 即時レジスタ・音符・音色、reserve／score／MMLを既存名・引数も含め比較する。
4. clock、総音量、FM gain、queue上限、gapless loop等を能力として宣言する。
5. 同じ元コードをbackendの生成部分だけ差し替えて走らせる契約試験を作る。

Rev Cも新APIを使えるようにadapterで移行する。旧ファームウェアへ新機能が追加済みとは扱わない。
WebLab側にadapterや仮想v2 deviceを導入する変更は、WebLabプロジェクトで別途実装する。
既存WebLabの同期I2C proxy、Worker境界、GC制約をこのハードウェア検討から変更しない。

## 契約試験の対象

独自の短い音列を入力にして、eventの順序と値・STOP後の未実行・状態を比較する。
ゲーム楽曲や録音を公開テストへ入れない。

- wire：破損CRC、形状、上限、snapshot、sequence周回・重複・再送・STOP再同期。
- session：原子的PUSH、満杯、SEAL不一致、同時刻順序、枯渇、100 ms超遅延、正常終端。
- safety：STOP、lease、音声fault、reset、USB切断、所有権、再接続だけで再発音しないこと。
- host：実際のRevCStreamとplayer、最終KEEPとDONEの競合、Ctrl+C後の消音。
- common API：音階／休符／和音／音色・音量の能力差、範囲外引数、未対応機能の明示拒否。

現在はフレームに加え、I2C target・session・FIFO・STOP／leaseをRTL実装し、
既存HOSTでの補充再生・repeat・中断／復帰をモデル試験した。[検証範囲](SESSION.md)。
全API／USB／実音源／実機の互換合格を示すものではない。

2026-11-15追補：[実YM音声RTL](AUDIO.md)をv2 sessionへ接続した。
既存HOST／Cのwireを変更せず、prepare再準備中のhealth低下と完了時判定を検証した。
初回音声対象は4MHz・合成時固定gain。可変clock／runtime gainのAPIは追加していない。

Si5351起動・可変clock追補：[CLOCKS.md](CLOCKS.md)。公開v2は4MHz-onlyのまま、
内部設定で4MHz以外が選ばれていれば、4MHz BEGINをDATA6で拒否する。
clock選択の公開コマンド・capabilityは未追加。0x42のHOSTバスと0x60の設定バスは別。


USB追補：[USB.md](USB.md)。USB-MIDIのC版6単音channel・Note/CC120/123/FFと
MIDI／I2C排他・切断時消音をRTLモデルで検証する。v2 wire／HOSTは無変更。
CDCはstatus/help/stop/s/Ctrl+C/panicの限定consoleで、C版console／REPL全体の互換ではない。
MIDIは4MHz専用、velocityによる音量、GM、pitch bend、sustain等は未対応。
USB reset・suspend・VBUS切断中でもI2C演奏を継続し、再接続で保留音符を再発音しない。
物理USB接続・OS列挙・F1実音の互換合格は未判定。


内部配置配線追補：[TIMING.md](TIMING.md)。v2 wireと既存HOST/playerは無変更。
FIFO時刻変換は段階化するが、due／100ms遅延期限の判定は現在時刻で行う。
USB-MIDI取出しの登録語もSTOP／切断／flushで破棄し、再接続だけでは再発音しない。
モデル回帰とECP5内部setup評価の結果を、物理IO・USB・実機の互換合格と区別する。
