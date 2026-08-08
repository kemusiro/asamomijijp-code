package jp.or.rim.kt.kemusiro.sound.tone;

/**
 * ダミーエンベロープをあらわすクラス。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class DummyEnvelope extends Envelope {
    public DummyEnvelope() {
    }

    protected double getValueInPressing() {
	return 1.0;
    }

    protected double getValueInReleasing() {
	return 1.0;
    }
}
