# review Eの検証範囲

2026-11-19。Python3.15.2、KiCad CLI10.0.5。

- `generate.py --check`：3基板のnative ERC（全警告込み）違反0、全pin/netのexport XML一致。ベース143参照/15page/114net、音源83参照/11page/81net、パネル51参照/9page/38net。
- `verify.py`：メーカー16SOP端子・全NC、2つのフォロワ帰還、CRB極性、33ΩのSD/SH/CLK接続、37FM/39SSG、base/panel電気部品の完全一致、全MCU GPIO・既存clock/I2S/STOP配線の保持を独立照合。
- 独自DACランドの16pad・番号方向・1.27mm・row/pad寸法を照合。一時PCBに読み込んだKiCad SVG exportも成功。これは音源PCB/DRCの実施ではない。現物装着未確認。
- 合計277参照と81購入行の一対一対応、数量・袋余り・支給DAC0円・各5枚/1セット・税送料予備枠の算術を照合。
- review C/Dと既存firmware等306ファイル、C以前の保存404ファイルのSHA-256を照合。重複を含む別集合であり710個のユニークファイルと称さない。
- native DACシートをSVGへ出力し、端子名・NC・CRBの+表示・ラベルの判読/重なりを目視確認。
- `git diff --check`、新資料のローカル参照と末尾空白、公開物へ個人ローカル絶対パスが入っていないことを確認。

Fontconfigのシステム設定警告はCLI stderrへ出たが、native ERCファイル内の違反ではない。警告除外やERC waiverを追加していない。

## 未実施

新PCB配置/配線/DRC/CAM、製造発注、実ランド合わせ、電源/バイアス/THD/SNR/発振/時計波形・FM/SSG校正、基板実機試験。部品モデルを使うSPICE・ソフトウェア実装/ビルド/動作テストも未実施（firmwareソースを変更していない）。静的レベル/slew計算はtypや仮定を含む設計チェックで、全温度/全個体の性能を証明しない。

ベースADC・I2Sは保持配線であり、この新基板で実装/稼働確認済みという意味ではない。HOST/MIDI/STOPの移植・実機回帰はCOMPATIBILITY.mdへ記載。
