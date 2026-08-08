package jp.or.rim.kt.kemusiro.sound;

import jp.or.rim.kt.kemusiro.sound.tone.SineWave;
import jp.or.rim.kt.kemusiro.sound.tone.Envelope;
import jp.or.rim.kt.kemusiro.sound.tone.SimpleEnvelope;

/**
 * sin波を表すクラス。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class SineWaveInstrument extends Instrument {
    public SineWaveInstrument() {
	wave = new SineWave();
	envelope = new SimpleEnvelope();
    }

    public SineWaveInstrument(Envelope envelope) {
	wave = new SineWave();
	this.envelope = envelope;
    }

    public String getName() {
	return toString();
    }

    public String toString() {
	return "Sine Wave";
    }
}
