package jp.or.rim.kt.kemusiro.sound;

import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.DataLine;

/**
 * データを演奏する操作を提供する抽象クラス。
 *
 * @version $Revision: 1.2 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public abstract class SoundPlayer {
    protected AudioFormat format;

    /**
     * サンプリングレートをfloatで返す。
     *
     * @return サンプリングレート
     */
    public float getSampleRate() {
	return format.getSampleRate();
    }

    /**
     * フレームサイズを返す。
     *
     * @return フレームサイズ
     */
    public int getFrameSize() {
	return format.getFrameSize();
    }

    /**
     * ラインを返す。
     *
     * @return ライン
     */
    public abstract DataLine getLine();

    /**
     * 再生を開始する。
     *
     */
    public void start() {
	getLine().start();
    }

    /**
     * バッファにたまっているデータを掃き出す。
     *
     */
    public void drain() {
	getLine().drain();
    }

    /**
     * 再生を終了する。
     *
     */
    public void stop() {
	getLine().stop();
    }

    /**
     * ラインを閉じる。
     *
     */
    public void close() {
	getLine().close();
    }
}
