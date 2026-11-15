# Rev C C SDK I2C streaming protocol v2 / 0.4.0-alpha.2

物理Rev C専用。7bitアドレス0x42、3.3V、操作側hardware I2C0 GP0/1→Rev C GP20/21。
最初の実機評価は100kHz。既存4.7kΩプルアップを使用し、GND/SDA/SCLだけを接続する。
旧MicroPython版のYM22F001・レジスタ窓・16バイト要求と非互換。新署名YM22S002を確認してから書く。
従来のv1ソース・受入済みZIPは保存する。WYM1のファイル形式とイベントの意味は変更しない。

## 転送

単一ホスト、要求は1件ずつ直列。要求全体を1回のwriteto(...,stop=True)で送る。
状態は別トランザクションのreadfrom(0x42,64,stop=True)。レジスタポインタを送らない。
Repeated-start、複数コントローラ、400kHzの実機動作は今回の受入対象外。
書込みSTOP後、末尾FIFOを取り込んでから要求を公開する。IRQ内でCRC、YM書込みや印字を行わない。
状態は読取り開始時に64バイトを固定し、そのトランザクション中に混在させない。65バイト目以降はFF。
受信FIFOは4要求×208バイト。超過や208バイトを超える転送はS_IOで停止し、黙って継続しない。

## 要求フレーム

little endian。長さは16+payload_length、最大208バイト。

| byte | 内容 |
| --- | --- |
| 0..1 | ASCII Y2 |
| 2 | version=2 |
| 3 | opcode |
| 4..7 | sequence uint32 |
| 8..9 | payload_length uint16、0..192 |
| 10..11 | reserved=0 |
| 12.. | payload |
| 末尾4 | CRC32/ISO-HDLC、先頭～payload末尾、little endian |

CRC32はbinascii.crc32互換、poly反射EDB88320、初期FFFFFFFF、最終xorFFFFFFFF。
sequenceはnext_seqから始め、成功で+1(mod2^32)。拒否は消費しない。
直前に成功した要求と同じsequence・全バイトの再送はACKだけ返し、再実行・リース延長しない。
同じsequenceで異なる要求はS_SEQUENCE。STOPはnext_seqがずれた場合も受理できるが、
直前と同じsequenceの異なる要求にはできない。通常は状態のnext_seqを読みSTOPを送る。
CRC/形状不正ではACK sequenceを信用できないので更新しない。最新resultのみを返す。
ホストはACK sequenceとnext_seqの両方を確認する。応答期限500ms、再送は同一バイトで1回まで。

| opcode | payload | 動作 |
| --- | --- | --- |
| 0 PING | なし | 疎通。リースを延長しない |
| 1 STOP | なし | 全出力消音、キュー破棄、全声停止。USB再生にも優先。次のBEGINまで再開しない |
| 2 BEGIN | WYM1ヘッダー16バイト＋ファイル全体CRC32 uint32 | 無音リセット、メタデータとCRC開始。PREFILLへ |
| 3 PUSH | WYM1レコード(timestamp_ms:uint32,register:uint8,value:uint8)×1..32 | 全件を検査して原子的に追加 |
| 4 PLAY | なし | PREFILLがmin(512,total)以上なら250ms後を時刻0として開始 |
| 5 KEEP | なし | PREFILL/RUNNINGのリース更新。失効後の再開はしない |
| 6 SEAL | なし | 全件受信とファイルCRC一致を確認。以後PUSH不可 |

BEGINはIDLE/STOPPED/DONEのみ。FAULTはSTOPで解除してからBEGIN。
USB内蔵BIN再生中や音声未準備ではBEGINを拒否する。
PUSHはPREFILL/RUNNINGのみ。時刻非減少、period以下、既存許可レジスタ、総件数と空き枠を検査する。
総件数は1..131071、clock=4MHz、periodは正のuint32ms。SSG I/Oやプリスケーラ等の禁止は従来どおり。
WYM1ヘッダーを含む全バイトのCRCを受信順に蓄積し、SEAL時にBEGINのCRCと照合する。

## 状態64バイト

| byte | 内容 |
| --- | --- |
| 0..7 | ASCII YM22S002 |
| 8 | major=2 |
| 9 | state:0 IDLE,1 PREFILL,2 RUNNING,3 DONE,4 STOPPED,5 FAULT |
| 10 | 最新要求のresult |
| 11 | flags:bit0 API稼働、bit1音声正常、bit2 RUNNING、bit3 SEALED、bit4 I2C所有、bit5リース失効 |
| 12..15 | ACK sequence、起動時FFFFFFFF |
| 16..19 | next_seq、起動時0 |
| 20..23 | 受信レコード数 |
| 24..27 | 適用済みレコード数 |
| 28..31 | total |
| 32..35 | period_ms |
| 36..37 | queued uint16 |
| 38..39 | free uint16 |
| 40..43 | 演奏基準からのelapsed_ms |
| 44..45 | セッション停止理由error uint16 |
| 46..47 | 演奏中のキュー下限uint16、末尾の正常な空も含む |
| 48..51 | 書込み開始遅延max_late_us |
| 52..55 | ヘッダーから受信済み末尾までのCRC32 |
| 56..59 | 状態生成番号uint32 |
| 60..63 | 先頭60バイトのCRC32 |

result/error:0 OK,1 CRC,2 SHAPE,3 SEQUENCE,4 STATE,5 FULL,6 DATA,7 IO,
8 LEASE,9 UNDERRUN,10 LATE,11 INTEGRITY,12 AUDIO。
要求拒否のresultと、既存セッションを停止したerrorは別。result=0だけで発音正常と扱わず、state/errorも確認する。

## 先読み・時刻・消音

キュー1024件。開始時刻はRev Cの64bit µs時計で管理し、各WYM1 timestamp_msを絶対オフセットとして使う。
I2Cの到着間隔で音符の長さを決めない。同時刻もファイル順でBUSYを待って適用し、欠落や順序交換をしない。
100ms超の書込み遅延、未受信分がある状態でのキュー枯渇、CRC不一致、音声異常はFAULT消音。
SEAL済み・全件適用後もperiodまで待ち、全声停止とゲートOFFを行ってDONEになる。
終端後の消音6書込みは楽曲イベント数に含めない。

成功したBEGIN/PUSH/PLAY/KEEP/SEALが1000msリースを更新する。読取り、PING、不正要求、重複は更新しない。
失効判定を要求受理より先に行い、遅れたKEEPで復帰させない。STOP→BEGINと全データの再送が必要。
USB接続の有無はI2C所有中のリースに影響しない。USBのSTOP/rebootは全体停止。
USBからplay/test/capture/bus変更はI2C所有中は拒否する。FMゲインはUSBから変更でき、既定100%。

100kHzで208バイト要求＋64バイト状態を送ると、アドレスを含む理想wire時間は約24.66ms。
32イベント/要求なので約1297件/秒に相当する。Python/CRC/待ち時間は別。
Ys II平均約413件/秒、最大1秒窓569件に対し先読みで余裕を持たせる設計。
これは電気的な実効速度の保証ではなく、実機受入で確認する。

alpha.2: BEGINの内部準備は、音声未準備・音声障害・リセット失敗ではS_AUDIO(12)とFAULTを返す。
USB再生中の所有権拒否はS_STATE(4)。失敗はsequenceを消費せず、STOPでセッションを解除する。
状態64バイトと要求フレームはalpha.1と同じ。
