package jp.or.rim.kt.kemusiro.sound.tone;

/**
 * 単純エンベロープをあらわすクラス。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class SimpleEnvelope extends Envelope {
    public SimpleEnvelope() {
    }

    protected double getValueInPressing() {
	return 1.0;
    }

    protected double getValueInReleasing() {
	return 0.0;
    }
}
