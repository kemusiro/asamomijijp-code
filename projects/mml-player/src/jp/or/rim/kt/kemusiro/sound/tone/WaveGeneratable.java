package jp.or.rim.kt.kemusiro.sound.tone;

/**
 * 音声を発生しうるインターフェース。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public interface WaveGeneratable {
    /**
     * 指定の時刻の値を得る。波形の振幅は1.0に正規化される。
     *
     * @param number 音番号(0-127)
     * @param time 時刻
     * @return 波形値
     */
    public double getValue(int number, double time);
}
