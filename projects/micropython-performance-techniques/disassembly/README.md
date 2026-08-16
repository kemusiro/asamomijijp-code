# native・Viper・インラインアセンブラの生成コード

ベンチマークで使ったnative、Viper、Thumbインラインアセンブラの各関数について、MicroPython 1.28.0が生成するARM Thumb命令を確認するための資料です。

## 前提

- ソース: `emitter-disassembly.py`
- クロスコンパイラー: MicroPython 1.28.0の`mpy-cross`
- 対象ABI: `armv7emsp`
- 逆アセンブラー: GNU Arm Embedded objdump 2.36.1
- 逆アセンブル指定: `-D -b binary -marm -Mforce-thumb`

実機の`sys.implementation`が示した`.mpy` ABIと同じ`armv7emsp`を指定しています。ただし、これはPico 2 WのRAMから関数を読み戻した結果ではありません。同じMicroPython版、ソース、ABIに対する`mpy-cross`出力であり、実機上のソースコンパイラーと共通のnativeエミッターが出す命令構造を再現するものです。絶対アドレスや実行時の配置を示す資料ではありません。

## 再現手順

MicroPython 1.28.0のソースツリーで`mpy-cross`をビルドし、次のように`.mpy`ファイルを作ります。

```console
mpy-cross -march=armv7emsp -o emitter-disassembly.mpy emitter-disassembly.py
python3 tools/mpy-tool.py -d emitter-disassembly.mpy
python3 tools/mpy-tool.py -e emitter-disassembly.mpy
```

`mpy-tool.py -e`が取り出した各nativeコード領域を、関数名と対応づけて逆アセンブルしました。native関数の先頭にある4-byteの`.mpy`側メタデータは除外しています。`armv7emsp-objdump.txt`の末尾に命令でないデータが見える箇所があるため、コード領域全体のbyte数を「純粋な命令サイズ」とは扱わないでください。

## 読み取れること

### native

`sum_native`の反復では、加算と減算ごとに関数テーブル経由で`binary_op`を呼び、`while n`の判定でも`obj_is_true`を呼びます。機械語へ変換されても、値はPythonオブジェクトのままで、Pythonの演算規則を実行時ヘルパーに委ねています。

`xor_native`でも、添字の読み書きは`obj_subscr`、XOR・加算・比較は`binary_op`、条件判定は`obj_is_true`を呼びます。バイトコードの命令ディスパッチは消えますが、オブジェクト操作そのものは残ります。

### Viper

`sum_viper`は関数入口で引数を`convert_obj_to_native`により機械語整数へ変換し、出口で`convert_native_to_obj`によりPython整数へ戻します。ループ内の加算、減算、比較、分岐は`adds`、`subs`、`cmp`、`bne`になります。

`xor_viper`も関数入口で整数と`ptr8`を変換した後、ループでは`ldrb`、`eors`、`strb`で1 byteを直接更新します。ただし、コンパイラーが生成したレジスター移動、スタックへの退避・復帰、`range`の比較処理も残ります。

### Thumbインラインアセンブラ

関数本体は記述した命令とほぼ一対一です。`sum_asm`の反復は`adds`、`subs`、`bne`、`xor_asm`の反復は`ldrb`、`eors`、`strb`、ポインター加算、カウンター減算、`bne`です。

一方で、MicroPythonは関数の入口と出口にABI用の`push`と`pop`を生成します。インラインアセンブラでも、関数呼び出し全体が記述したループ命令だけになるわけではありません。
