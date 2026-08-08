package jp.or.rim.kt.kemusiro.sound;

import jp.or.rim.kt.kemusiro.sound.tone.SquareWave;
import jp.or.rim.kt.kemusiro.sound.tone.Envelope;
import jp.or.rim.kt.kemusiro.sound.tone.SimpleEnvelope;

/**
 * 方形波を表すクラス。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class SquareWaveInstrument extends Instrument {
    public SquareWaveInstrument() {
	wave = new SquareWave();
	envelope = new SimpleEnvelope();
    }

    public SquareWaveInstrument(Envelope envelope) {
	wave = new SquareWave();
	this.envelope = envelope;
    }

    public String getName() {
	return toString();
    }

    public String toString() {
	return "Square Wave";
    }
}
