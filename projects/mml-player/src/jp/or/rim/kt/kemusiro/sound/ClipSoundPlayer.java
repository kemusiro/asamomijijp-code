package jp.or.rim.kt.kemusiro.sound;

import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.Clip;
import javax.sound.sampled.DataLine;
import javax.sound.sampled.LineUnavailableException;

/**
 * すでにできあがったバイト配列を演奏する。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class ClipSoundPlayer extends SoundPlayer {
    private Clip line = null;

    /**
     * 音声再生用のオブジェクトを生成する。
     *
     * @param rate サンプリングレート
     * @param depth サンプリングビット長
     * @param array 再生する音声データの配列
     */
    public ClipSoundPlayer(int rate, int depth, byte[] array) {
	format = new AudioFormat(AudioFormat.Encoding.PCM_SIGNED,
				 (float)rate, depth, 1, 1, (float)rate, true);
	DataLine.Info info = new DataLine.Info(Clip.class, format);
	try {
	    line = (Clip)AudioSystem.getLine(info);
	    line.open(format, array, 0, array.length);
	}
	catch (LineUnavailableException e) {
	    e.printStackTrace();
	}
    }

    /**
     * ラインを返す。
     *
     * @return ライン
     */
    public DataLine getLine() {
	return line;
    }

}
