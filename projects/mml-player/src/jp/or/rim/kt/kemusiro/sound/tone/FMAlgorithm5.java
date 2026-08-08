package jp.or.rim.kt.kemusiro.sound.tone;

/**
 * FM音源のアルゴリズム5。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class FMAlgorithm5 extends FMAlgorithm {
    public FMAlgorithm5(FMParameter p) {
	super(4);

	SawWave pitch = new SawWave();
	setInput(0, pitch, null);
	setInput(1, pitch, getOperator(0));
	setInput(2, pitch, getOperator(0));
	setInput(3, pitch, getOperator(0));
	setParameter(p);
    }

    public double getValue(int number, double time) {
	return (getOperator(1).getValue(number, time) +
		getOperator(2).getValue(number, time) +
		getOperator(3).getValue(number, time)) / 3.0;
    }
}
