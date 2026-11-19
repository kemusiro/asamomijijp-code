# 次期音源基板：P2ベース＋交換式音源基板

2026-11-19。**ベースL・4層＋音源K・2層＋開口なしシールドB・2層を主案として採用する。**
今回の発注準備入口は[購入資料review B：各5枚・部品1セット](primary-order-review-b/README.md)。
追加の価格・販売単位調査は[調達確認review C](procurement-review-c/README.md)。L4/K2/B2の送料比較と未確定56行＋C14別調達先を記録した。
3基板の製造用Gerber、購入用CSV/Excel、調達先別一覧、数量とSHAをまとめた。PCBは計15枚、実装3枚、予備12枚。
P2実機受入・現物嵌合・部品確認事項は未完、PCB発注・部品購入・支払いは未実施。

**主案ベースのUSB-C修正版**：[review L](clean-sheet-pcb-review-l/README.md)を新規作成した。
[部品適合review A](preorder-review-a/README.md)のJUSB寸法差を修正し、ERC/DRC/未配線/回路図差分0、571pad・G40/UNO接点とCAMを照合。
ベース4層・音源2層、各5枚・部品1セットの条件を維持する。旧Jと既存J4/K2/B2の注文一式は保存履歴。
新L4/K2/B2の製造ZIPと購入CSV/Excelを別版としてまとめた。CACL/CACRはGRM21BZ71C106KE15Lを試作採用した。
DC/小信号ACの代表曲線による選別であり、複合条件の容量保証・実測ではない。現物嵌合・新Gerberの確定見積は未完。

[2層比較版K](clean-sheet-pcb-review-k/README.md)のベースは比較用として保存し、今回の発注には含めない。
[層構成の検討A](layer-study-review-a/README.md)、J/Iの旧CADと従来の製造・見積記録も保持する。
[製造・送料比較K](manufacturing-review-k/README.md)は両案の検証・見積の記録で、今回の選択は主案注文資料を正本とする。
G40・UNO・GPIO・HOST/USB-MIDI・停止仕様は維持する要件。新PCBでの実機合格は未確認。

| 資料 | 内容 |
| --- | --- |
| [調達確認review C](procurement-review-c/README.md) | L4/K2/B2各5枚の送料込み参考比較、57行の購入先/販売条件、廃番・在庫0・残件の区別 |
| [今回の発注準備review B](primary-order-review-b/README.md) | L4/K2/B2、各5枚・部品1セット。USB修正版・C14試作選定・90購入行・Excel・現物確認票 |
| [旧主案注文一式](primary-order-5pcb-1set/README.md) | J4/K2/B2の保存記録。旧USBランドを含むため今回の発注に混在させない |
| [製造・送料比較K](manufacturing-review-k/README.md) | 4種類のCAM・個別ZIP、主案4/2と比較2/2の各5枚・部品1セット見積 |
| [2層比較版K](clean-sheet-pcb-review-k/README.md) | 新規2層PCB・13抵抗の配置変更・電気/積層照合。従来CADを保存 |
| [層構成の検討A](layer-study-review-a/README.md) | 主案4/2と比較案2/2。既存内層配線の読取監査、GND/USB/音声・電源・製造比較の方針。当時は新CAD未作成の保存記録 |
| [今回の購入表・PCB送料比較](manufacturing-review-j/procurement/order-5pcb-1set/README.md) | 基板各5枚・部品1セット。15枚中3枚実装、12枚予備。JLCPCB/PCBWay匿名送料見積、数量計算を更新 |
| [製造Gerber・購入用部品表](manufacturing-review-j/README.md) | 3枚のGerber/Excellon・新規ERC/DRC0、90購入行・274参照対応。未確定容量/嵌合条件あり |
| [review J PCB・BOM・検証](clean-sheet-pcb-review-j/README.md) | 配置配線済みCADと12電気契約＋18積層契約・6回帰試験 |
| [配置図](clean-sheet-pcb-review-j/layout.svg) / [組立・高さ](clean-sheet-pcb-review-j/ASSEMBLY.md) | 対向面間・ソケット・UNO・6か所のビア先埋め条件 |
| [電源・配線](clean-sheet-pcb-review-j/POWER-ROUTING.md) | GND参照面、電源補助面、USB/音声の記録と測定課題 |
| [H回路](clean-sheet-schematic-review-h/README.md) | 改変しない電気設計の参照元 |
| [G接点/GPIO](clean-sheet-interface-review-g/README.md) | G40/KEY6のpin配置元 |
| [P2構成](P2-MODULAR.md) / [接続I/F](P2-MODULE-INTERFACE.md) | 現主案への入口 |
| [音源比較](P2-SOUND-MODULES.md) | PSG・音声合成・ラジオ等の候補 |

既存HOST opn1・4MHz、USB-MIDI/所有権/STOP/lease、UNO外部機能を維持する要件。
base44/47 GPIO、予備35～37、source28/46 GPIO。旧base/cardの物理互換は要求しない。
P2 firmwareと実機回帰、実部品の嵌合、電源・USB・熱・音声の測定は未完。DRC0を製造/実機合格と扱わない。
[active-plan.json](active-plan.json)と[p2-modular-plan.json](p2-modular-plan.json)を正本入口とし、過去の設計・受入は保存する。

音色編集用の[UNOシールド review B](editor-shield-review-b/README.md)も設計した。
秋月調達優先の4ノブ・encoder・1.54インチLCD・64音色EEPROM保存・USB CDC JSON取得の仕様と接続済み回路図。
ERC0、32接点/159pad照合、保存等13モデル試験。購入小計3,160円（基板等別）。
回路図review A/Bと開口付きPCBは保存。review Bの[開口なし2層PCB](editor-shield-review-b/pcb-review-b/README.md)へ更新し、
ERC/DRC/未配線/回路図差分0、166padと32嵌合座標を照合。LCD・シールド形状とUNO座標は維持。
JではDIP・ベースSTOP/TESTを音源基板の右へ移し、音源から最小11.225mm。シールドの開口・切欠き0。
シールド下面のSMT空間4.5mm等は条件付きモデル。現物嵌合・P2 firmware・実機受入は未完。
旧[review I](clean-sheet-pcb-review-i/README.md)と、その上に載るシールドBの過去の検査記録も保存する。

## F1の実装・検証資産（保持）

[F1 FPGA単独案](FPGA-STANDALONE.md)と[RTL](../../fpga-standalone/README.md)は
再利用・比較資産として保持する。FPGAを使わないP2へ検証結果を流用しない。
F1のI2C／音声／可変clock／USB RTL、ULX3S 85Fの49padと3 seed通常P&R、
[165部品のキャリア回路図レビューA](carrier-f1/README.md)、
[Diamond準備](../../fpga-standalone/boards/ulx3s/diamond/README.md)の記録を残す。
F1のDiamond実行・PCB・実機受入も未完。

## 比較資料と過去の検討

旧案・実測値は、それぞれの条件での記録として残す。P2の資源や実機合格へ流用しない。
M1のJSON内statusは検討時点の記録であり、現在の主案P2はactive-plan.jsonで判断する。

| 資料 | 元の条件 |
| --- | --- |
| [M1](MODULE-HAND-SOLDERED.md) | Pico 2＋UP5Kモジュール、狭ピッチ手実装。31本の旧端子予算 |
| [旧直接実装案](INITIAL-DIRECT-MOUNT.md) | 裸UP5K、Picoからの構成ロード、業者SMT等 |
| [実装・小型化案](ASSEMBLY-AND-SIZE.md) | 直接実装と片面SMT・部分委託の比較 |
| [Economic BOM](ECONOMIC-BOM.md) | 5枚、業者SMT、2 mm以上の自前実装 |
| [H1](HAND-SOLDERED.md) | 1.27 mm以上、Si5351・DACもモジュール |
| [JT03音源内蔵RTL](../../fpga-jt03-minimal/README.md) | 実YMをFPGA内音源へ置換、固定4 MHz相当 |
| [旧算術検証一覧](verification/README.md) | 旧条件の入力・算術・資料整合性 |

Rev Cの承認済みGPIO・UF2・受入結果は維持する。
review Jと開口なしシールドの製造データ・購入候補を[製造準備資料](manufacturing-review-j/README.md)へ追加した。
現在の購入条件は[review B：基板各5枚・部品1セット](primary-order-review-b/README.md)。
従来の1/5セット比較と製造検証記録は保存し、今回の数量表・見積を別記録にした。
ADC結合Cの複合条件実測・ソケット等の現物合わせ・新Gerber確定見積・部品購入・P2実機受入は未完了。

I2C制御部分の[実装・検証結果](../../fpga-standalone/SESSION.md)を追加した。

## P2 revision 2.1 回路図レビューA（保存履歴）

[carrier-p2](carrier-p2/README.md)にPGA2350実端子、UNO R3形状3.3Vヘッダー、
周辺回路の接続済みKiCad回路図と未配線配置確認データを追加した。
GPIO47本の周辺機能静的照合、全netlist一致、ERC違反0件。
既存HOSTは未変更。このA時点では配線済みPCBは未作成。一体型の配線候補は下記のレビューBを参照。P2ファームウェア移植・実機受入は未完。

## P2 revision 2.1 / PCBレビューB（分離前の保存履歴）

[レビューB](carrier-p2/pcb-review-b/README.md)に電源容量・ソケット高さの検討と、
164部品の回路図・配線済み4層PCB候補を追加した。DACとUNO 3V3供給を500mA AUX LDOへ分離し、
PGA2350内蔵300mA電源の設計予算を259.4mAとした。一般2列ソケット4個は端部が干渉するため、
64本の単端子ソケットを候補にし、実物の挿入・保持・高さ確認を残す。
47 GPIO、UNO接点座標、既存HOSTは変更しない。回路・DRCの結果はBの検査記録を参照。
P2専用ファームウェア、実組立、電流・温度・USBインピーダンスの確認、製造リリースは未完。
レビューAの回路図と検査記録は履歴として保存する。

購入予算の最新追補は[review D：残る18行・代替候補・送料込み総額](procurement-review-d/README.md)。
YM2203CはRev Cから流用、部品は1セット、基板は各5枚。B/CとCADを保存した別の購入候補計算であり、発注・実機受入は未実施。

UNO形状を廃止し音色編集を残す[低コスト別案LC-A](low-cost-review-a/README.md)を追加した。
Picossci直付け・一般連結ソケット・0.3mmビア・鉛フリーHASLの構成と条件付き予算を比較。現行L/K/Bとactive-planを保存した検討資料で、新CAD/firmware/実機受入ではない。

3.3V I2C編集パネルと小型ベースMCUの[低コスト別案LC-B](low-cost-review-b/README.md)を追加した。
Picossci 2 RP2350A＋Pico RP2040パネル＋Groveの端子候補・電源・停止処理・費用を比較。
既存L/K/B・LC-A・HOST・firmwareを保存した未適用の構成検討であり、新CAD・実機受入ではない。

LC-BのGPIOを採用した[接続済み回路図review C](low-cost-schematic-review-c/README.md)を追加した。
base143・source73・panel51参照、3枚ともnative ERC0。汎用品・3店同梱へ見直し、各5枚/部品1セットで送料・予備枠込み約3万円を目標とする。
旧L/K/BとLC-A/B、active-plan、Rev C firmware/HOSTは保存。新PCB/DRC/firmware/実機受入ではない。

音声経路の最新方針は[LC audio review D：YM3014B-F＋共通ADC・I2S維持](low-cost-audio-review-d/README.md)。
YM2203はFM/SSG分離アナログ、将来音源はI2S＋アナログ併用に対応する設計契約。
約3万円・各5枚/部品1セットを目標に、source MCU・共通ADC・出力DACを維持する。
回路図C・承認GPIO・HOST/firmwareは保存し、Dの回路化/ERC/実機受入は次工程。

YM3014B-F採用の[接続済み回路図review E](low-cost-ym3014-schematic-review-e/README.md)を追加した。
G40の37=アナログFM、39=アナログSSG、base ADC/I2S/DACと全GPIOを維持。
新音源83参照、3基板native ERC0、全277参照/81購入行、各5枚/部品1セットの送料・予備枠込み概算29,936円。
C/D・既存HOST/firmwareは保存。新PCB/DRC・firmware・実機受入は未完。

review Eの回路を維持した[配線済みPCB review F](low-cost-ym3014-pcb-review-f/README.md)を追加した。ベース100×100mm・4層、音源100×80mm・2層、パネル100×76mm・2層。ネイティブERC/DRC、全277参照の端子・ネット、40接点の嵌合座標を検証。各5枚・部品1セットは送料込み29,936円の計画枠で、CAM確定見積とP2実機受入は未実施。

review Fの[製造・購入資料 G](low-cost-ym3014-manufacturing-review-g/README.md)を追加した。3基板各5枚のGerber/Excellonと86行の購入表、送料・予備費込み約28,103円の計画。CAMの外形・銅層・全穴とFを照合し、ERC/DRC0、277参照を購入表と照合。元のFとHOST/firmwareは保存。最終カート・在庫確認・P2実機受入は未実施。ZIP/XLSXはGit管理外へローカル生成する。

購入表の最新追補は[review H：在庫3行と価格11行の調達確認](low-cost-ym3014-procurement-review-h/README.md)。F/Gを保存し、277参照・86購入行を維持。1µFを同仕様のWürth品へ、LDOは同じTI型番をMouser調達へ変更し、秋月中心の各5枚/部品1セットで送料枠・予備費込み約30,050円。Mouser少額送料は未確定の2,500円枠、最終カート・現物確保・P2実機受入は未実施。

購入表の最新追補は[review I：海外43行をMouserへ集約](low-cost-ym3014-procurement-review-i/README.md)。秋月・スイッチサイエンスを第1・第2優先に維持し、F/G/HのCAD・HOST/firmwareを保存。各5枚/部品1セット、送料・部品税・予備費込み概算26,684円。43行の掲載価格・販売単位・在庫を照合したが3行は在庫0、21行は外貨掲載から予算換算。日本円カート・欠品納期・最終配送額は未確定。

購入資料の最新追補は[review J：欠品3行の代替と在庫優先の基板変更候補](low-cost-ym3014-procurement-review-j/README.md)。
現Fの277参照・86行を維持し、ロジック2品を同パッドのQ1/E4品へ変更した購入候補は送料・税・予備費込み約27,217円。Si5351A GT/GTRは欠品のまま。
追加方針により、秋月650円のSi5351Aモジュールを使う次期ベース基板変更を推奨し、水晶等の削減未控除で約27,454円を比較する。
秋月・SS優先と海外Mouser集約を維持。Jは購入・接続の比較資料で、F/G/H/I・現CAD・HOST/firmwareを保存。新モジュール用の配置配線/ERC/DRC、最終カート・実機受入は未実施。

LC案の最新CADは[秋月Si5351Aモジュール採用 review K](low-cost-ym3014-pcb-review-k/README.md)。
F/G/H/I/Jを保存した別リビジョンで、U13を110679へ置換し旧Y1を削除。調達Jの同パッドQ1/E4ロジックも採用した。
ベース100×100mm/4層・音源100×80mm/2層・パネル100×76mm/2層、G40全40接点・GPIO・既存HOST/USB-MIDI/停止処理の設計契約を維持。
3枚ともERC/DRC/未接続/回路図差分0、全276参照を照合。各5枚・部品1セット、送料・税・予備費込み概算27,358.48円。
クロックは25MHz/0x60を維持し、P2 firmwareではCL8pFの初期化が必要。モジュール6mm以下・基板間12mmの条件で高さを整理した。
新Gerberと最終カート、P2 firmware移植、現物嵌合・電源/熱/波形・HOST/MIDI実機受入は未実施。

review Kの[製造・購入資料 L](low-cost-ym3014-manufacturing-review-l/README.md)を追加した。
3種各5枚のGerber/Excellon/ZIPと、部品1セットの85行購入表・購入先別CSV/XLSXを準備。
Kを変更せず、ERC/DRC/未接続/回路図差分0、CAM外形・銅層構成・全920穴/長穴を照合し、負例7件を検出。
秋月・SS優先/海外Mouser集約を維持。JLCPCBの仕様手入力価格と日本1kg送料を再確認し、送料・税・予備費込み概算27,358.48円。
Gerberアップロード後の業者CAM審査・最終カート・全85行の部品在庫確保・P2実機受入は未完。旧F/G/J/KとHOST/firmwareは保存。

公開前の再検証と個人設定ファイルを除いた保存ハッシュ一覧の扱いは、[review K/L公開記録](publication-review-kl/README.md)を参照。元の検証一覧・過去の検査報告は履歴として保持する。
