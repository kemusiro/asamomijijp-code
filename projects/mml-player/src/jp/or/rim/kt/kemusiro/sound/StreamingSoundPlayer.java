package jp.or.rim.kt.kemusiro.sound;

import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.SourceDataLine;
import javax.sound.sampled.DataLine;
import javax.sound.sampled.LineListener;
import javax.sound.sampled.LineUnavailableException;

/**
 * ストリー民具データを演奏する。
 *
 * @version $Revision: 1.2 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class StreamingSoundPlayer extends SoundPlayer {
    private SourceDataLine line = null;

    /**
     * 音声再生用のオブジェクトを生成する。
     *
     * @param rate サンプリングレート
     * @param depth サンプリングビット長
     */
    public StreamingSoundPlayer(int rate, int depth, LineListener listener) {
	format = new AudioFormat(AudioFormat.Encoding.PCM_SIGNED,
				 (float)rate, depth, 1, 1, (float)rate, true);
	DataLine.Info info = new DataLine.Info(SourceDataLine.class,
					       format);
	try {
	    line = (SourceDataLine)AudioSystem.getLine(info);
	    if (listener != null) {
		line.addLineListener(listener);
	    }
	    line.open(format);
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

    /**
     * ストリームにデータを出力する。
     *
     * @param value 再生するデータ
     */
    public void write(byte[] buffer, int offset, int length) {
	line.write(buffer, offset, length);
    }
}
