package jp.or.rim.kt.kemusiro.sound.tone;

/**
 * FM音源のアルゴリズム2。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class FMAlgorithm2 extends FMAlgorithm {
    public FMAlgorithm2(FMParameter p) {
	super(4);

	SawWave pitch = new SawWave();
	setInput(0, pitch, null);
	setInput(1, pitch, null);
	setInput(2, pitch, getOperator(1));
	setInput(3, getOperator(0), getOperator(2));
	setParameter(p);
    }

    public double getValue(int number, double time) {
	return getOperator(3).getValue(number, time);
    }
}
